# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/21_engines.icevision.predict.ipynb (unless otherwise specified).

__all__ = ['AllDataParser', 'icevision_tta', 'predict_bboxes_icevision', 'predict_instance_masks_icevision']

# Cell
from ...imports import *
from ...processing.all import *
from ...metrics import *
from .models import *

from fastcore.foundation import *
from fastcore.script import *

from icevision.all import *
from shutil import rmtree
from icevision.data.convert_records_to_coco_style import coco_api_from_preds

# Cell

class AllDataParser(parsers.Parser):
    "Read all image files from data_dir, used with IceVision models"
    def __init__(self, data_dir):
        super().__init__(template_record=ObjectDetectionRecord())
        self.data_dir = data_dir

    def __iter__(self) -> Any:
        yield from get_image_files(self.data_dir)

    def __len__(self) -> int:
        return len(os.listdir(self.data_dir))

    def record_id(self,o) -> Hashable: return o

    def parse_fields(self, o, record, is_new):
        record.set_img_size(get_img_size(o))
        record.set_filepath(o)

# Cell

def icevision_tta(model_type, items, model) -> list:
    "Simple TTA with horizontal and vertical flips as augmentations"
    infer_tfms = tfms.A.Adapter([tfms.A.Normalize()])
    hflip_tfms = tfms.A.Adapter([tfms.A.Normalize(), tfms.A.HorizontalFlip(p=1)])
    vflip_tfms = tfms.A.Adapter([tfms.A.Normalize(), tfms.A.VerticalFlip(p=1)])

    infer_ds = Dataset(items, infer_tfms)
    infer_dl = model_type.infer_dl(infer_ds, batch_size=4, shuffle=False)

    vflip_ds = Dataset(items, vflip_tfms)
    vflip_dl = model_type.infer_dl(vflip_ds, batch_size=4, shuffle=False)

    hflip_ds = Dataset(items, hflip_tfms)
    hflip_dl = model_type.infer_dl(hflip_ds, batch_size=4, shuffle=False)

    preds = model_type.predict_from_dl(model=model, infer_dl=infer_dl, keep_images=False)
    vpreds = model_type.predict_from_dl(model=model, infer_dl=vflip_dl, keep_images=False)
    hpreds = model_type.predict_from_dl(model=model, infer_dl=hflip_dl, keep_images=False)

    for i, p in tqdm(enumerate(vpreds)):
        for j in rangeof(p.pred.detection.label_ids):
            p_mask = p.pred.detection.mask_array.to_mask(p.height, p.width).data[j]
            p.pred.detection.mask_array.data[j] = np.flipud(p_mask)

    for i, p in tqdm(enumerate(hpreds)):
        for j in rangeof(p.pred.detection.label_ids):
            p_mask = p.pred.detection.mask_array.to_mask(p.height, p.width).data[j]
            p.pred.detection.mask_array.data[j] = np.fliplr(p_mask)

    preds.extend(vpreds)
    preds.extend(hpreds)
    return preds

# Cell

@call_parse
def predict_bboxes_icevision(path_to_model_config:Param("Path to pretrained model folder",type=str),
                             path_to_image:Param("Path to image to annotate", type=str),
                             outfile:Param('Path and filename for output raster', type=str),
                             processing_dir:Param("Directory to save the intermediate tiles. Deleted after use", type=str, default='temp'),
                             tile_size:Param("Tile size to use. Default 400x400px tiles", type=int, default=400),
                             tile_overlap:Param("Tile overlap to use. Default 100px", type=int, default=200),
                             num_classes:Param("Number of classes to predict. Default 2", type=int, default=2),
                             use_tta:Param("Use test-time augmentation", store_true)

    ):
    "Detect bounding boxes from a new image using a pretrained model"
    if os.path.exists(processing_dir):
        print('Processing folder exists')
        return
    os.makedirs(processing_dir)
    print(f'Reading and tiling {path_to_image} to {tile_size}x{tile_size} tiles with overlap of {tile_overlap}px')
    tiler = Tiler(outpath=processing_dir, gridsize_x=int(tile_size), gridsize_y=int(tile_size),
                  overlap=(int(tile_overlap), int(tile_overlap)))
    tiler.tile_raster(path_to_image)

    # Check whether is possible to use gpu
    device = 'cpu' if not torch.cuda.is_available() else f'cuda:{torch.cuda.current_device()}'

    # Loading pretrained model
    print('Loading model')
    faster_rcnn = models.torchvision.faster_rcnn
    #state_dict = torch.load(path_to_model, map_location=device)
    #model = faster_rcnn.model(num_classes=len(class_map))
    #model.load_state_dict(state_dict)
    #if device != 'cpu': model.to(torch.device('cuda'))

    with open(f'{path_to_conf}/config.json') as conf:
        conf_dict = json.load(conf)

    class_map = ClassMap(list(range(1, len(conf_dict['categories']+1))))
    #state_dict = torch.load(path_to_model, map_location=device)
    model = load_mask_rcnn_from_config(path_to_model_config)#mask_rcnn.model(num_classes=len(class_map))

    infer_tfms = tfms.A.Adapter([tfms.A.Normalize()])

    print('Starting predictions')
    infer_parser = AllDataParser(data_dir=f'{processing_dir}/raster_tiles')
    infer_set = infer_parser.parse(data_splitter=SingleSplitSplitter(), autofix=False)[0]

    if use_tta:
        preds = icevision_tta(faster_rcnn, infer_set, model)
    else:
        infer_ds = Dataset(infer_set, infer_tfms)
        infer_dl = faster_rcnn.infer_dl(infer_ds, batch_size=16, shuffle=False)
        preds = faster_rcnn.predict_from_dl(model=model, infer_dl=infer_dl, keep_images=True)

    preds_coco = bbox_preds_to_coco_anns(preds)

    # TODO fix categories to not be hardcoded
    preds_coco['categories'] = conf_dict['categories']#[
        #{'supercategory':'deadwood', 'id':1, 'name': 'Standing'},
        #{'supercategory':'deadwood', 'id':2, 'name': 'Fallen'},
    #]

    # Process preds to shapefiles
    coco_proc = COCOProcessor(data_path=processing_dir,
                              outpath=processing_dir,
                              coco_info=None, coco_licenses=None,
                              coco_categories=preds_coco['categories'])


    coco_proc.coco_to_shp(preds_coco)

    # Discard all predictions that are not completely within -2m erosion of grid cell
    # TODO add as optional postprocessing step?

    grid = tiler.grid

    for cell in grid.itertuples():
        if not os.path.isfile(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson'): continue
        pred_shp = gpd.read_file(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')
        cell_geom = cell.geometry.buffer(-1) # 2 meter erosion from the edge
        pred_shp['to_drop'] = pred_shp.apply(lambda row: 0 if row.geometry.within(cell_geom) else 1, axis=1)
        pred_shp = pred_shp[pred_shp.to_drop == 0]
        pred_shp.drop(columns=['to_drop'], inplace=True)
        if use_tta:
            pred_shp = do_nms(pred_shp, 0.1, 'score')
        if len(pred_shp) > 0: pred_shp.to_file(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')
        else: os.remove(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')


    # Collate shapefiles
    untile_vector(path_to_targets=f'{processing_dir}/predicted_vectors', outpath=outfile)

    print('Removing intermediate files')
    rmtree(processing_dir)
    return


# Cell

@call_parse
def predict_instance_masks_icevision(path_to_model_config:Param("Path to pretrained model folder",type=str),
                                    path_to_image:Param("Path to image to annotate", type=str),
                                    outfile:Param('Path and filename for output raster', type=str),
                                    processing_dir:Param("Directory to save the intermediate tiles. Deleted after use", type=str, default='temp'),
                                    tile_size:Param("Tile size to use. Default 400x400px tiles", type=int, default=400),
                                    tile_overlap:Param("Tile overlap to use. Default 100px", type=int, default=200),
                                    #num_classes:Param("Number of classes to predict. Default 2", type=int, default=2),
                                    use_tta:Param("Use test-time augmentation", store_true),
                                    smooth_preds:Param("Run fill_holes and dilate_erode to masks", store_true)
    ):
    "Segment instance masks from a new image using a pretrained model"

    if os.path.exists(processing_dir):
        print('Processing folder exists')
        return
    os.makedirs(processing_dir)
    print(f'Reading and tiling {path_to_image} to {tile_size}x{tile_size} tiles with overlap of {tile_overlap}px')
    tiler = Tiler(outpath=processing_dir, gridsize_x=int(tile_size), gridsize_y=int(tile_size),
                  overlap=(int(tile_overlap), int(tile_overlap)))
    tiler.tile_raster(path_to_image)

    # Check whether is possible to use gpu
    device = 'cpu' if not torch.cuda.is_available() else f'cuda:{torch.cuda.current_device()}'
    mask_rcnn = models.torchvision.mask_rcnn
    # Loading pretrained model
    print('Loading model')

    with open(f'{path_to_model_config}/config.json') as conf:
        conf_dict = json.load(conf)

    class_map = ClassMap(list(range(1, len(conf_dict['categories'])+1)))
    #state_dict = torch.load(path_to_model, map_location=device)
    model = load_rcnn_from_config(path_to_model_config)#mask_rcnn.model(num_classes=len(class_map))

    #model.load_state_dict(state_dict)
    #if device != 'cpu': model.to(torch.device('cuda'))
    infer_tfms = tfms.A.Adapter([tfms.A.Normalize()])

    print('Starting predictions')
    infer_parser = AllDataParser(data_dir=f'{processing_dir}/raster_tiles')
    infer_set = infer_parser.parse(data_splitter=SingleSplitSplitter(), autofix=False)[0]
    if use_tta:
        preds = icevision_tta(mask_rcnn, infer_set, model)
    else:
        infer_ds = Dataset(infer_set, infer_tfms)
        infer_dl = mask_rcnn.infer_dl(infer_ds, batch_size=16, shuffle=False)
        preds = mask_rcnn.predict_from_dl(model=model, infer_dl=infer_dl, keep_images=True)

    # Mask postprocessing:
    if smooth_preds:
        preds = fill_holes(preds)
        preds = dilate_erode(preds)

    preds_coco = icevision_mask_preds_to_coco_anns(preds)
    # TODO fix categories to not be hardcoded
    preds_coco['categories'] = conf_dict['categories']#[
        #{'supercategory':'deadwood', 'id':1, 'name': 'Standing'},
        #{'supercategory':'deadwood', 'id':2, 'name': 'Fallen'},
    #]



    # Process preds to shapefiles
    coco_proc = COCOProcessor(data_path=processing_dir,
                              outpath=processing_dir,
                              coco_info=None, coco_licenses=None,
                              coco_categories=preds_coco['categories'])


    coco_proc.coco_to_shp(preds_coco, downsample_factor=1)

    # Discard all predictions that are not completely within -2m erosion of grid cell
    # TODO add as optional postprocessing step

    grid = tiler.grid
    grid = grid.to_crs('EPSG:3067')

    for cell in grid.itertuples():
        if not os.path.isfile(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson'): continue
        pred_shp = gpd.read_file(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')
        orig_crs = pred_shp.crs
        pred_shp = pred_shp.to_crs('EPSG:3067')
        cell_geom = cell.geometry.buffer(-1) # 1 unit erosion (~25px) from each side, hope that crs unit is meters.
        pred_shp['to_drop'] = pred_shp.apply(lambda row: 0 if row.geometry.within(cell_geom) else 1, axis=1)
        pred_shp = pred_shp[pred_shp.to_drop == 0]
        pred_shp = pred_shp.to_crs(orig_crs)
        pred_shp.drop(columns=['to_drop'], inplace=True)
        if use_tta:
            pred_shp = do_nms(pred_shp, 0.1, 'score')
        if len(pred_shp) > 0: pred_shp.to_file(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')
        else: os.remove(f'{processing_dir}/predicted_vectors/{cell.cell}.geojson')

    # Collate shapefiles
    untile_vector(path_to_targets=f'{processing_dir}/predicted_vectors', outpath=outfile)

    print('Removing intermediate files')
    rmtree(processing_dir)
    return