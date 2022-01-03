# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/08_predict.ipynb (unless otherwise specified).

__all__ = ['AllDataParser', 'icevision_tta', 'predict_bboxes', 'predict_instance_masks_detectron2',
           'predict_instance_masks_icevision', 'predict_segmentation']

# Cell
from .imports import *
from .utils import *
from .tiling import *
from .coco import *
from .metrics import *
from .losses import *
from .postproc import *
from .models import *

from fastcore.foundation import *
from fastcore.script import *

from fastai.vision.all import *
from fastai.learner import load_learner, Learner
from icevision.all import *

from fastai.data.load import DataLoader
from fastcore.transform import Pipeline

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

@patch
def remove(self:Pipeline, t):
    "Remove an instance of `t` from `self` if present"
    for i,o in enumerate(self.fs):
        if isinstance(o, t.__class__): self.fs.pop(i)
@patch
def set_base_transforms(self:DataLoader):
    "Removes all transforms with a `size` parameter"
    attrs = ['after_item', 'after_batch']
    for i, attr in enumerate(attrs):
        tfms = getattr(self, attr)
        for j, o in enumerate(tfms):
            if hasattr(o, 'size'):
                tfms.remove(o)
        setattr(self, attr, tfms)

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
def predict_bboxes(path_to_model_config:Param("Path to pretrained model folder",type=str),
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

import detectron2
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
import cv2

@call_parse
def predict_instance_masks_detectron2(path_to_model_config:Param("Path to pretrained model folder",type=str),
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

        # Loading pretrained model
    print('Loading model')

    cfg = get_cfg()
    cfg.merge_from_file(path_to_model_config)
    cfg.DEVICE = device

    print('Starting predictions')
    image_files = os.listdir(f'{processing_dir}/raster_tiles')
    if use_tta:
        print('Not yet implemented')
    #else:

    cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, 'model_final.pth')
    predictor = DefaultPredictor(cfg)

    images = []
    preds = []

    for i in tqdm(rangeof(image_files)):
        img = cv2.imread(f'{processing_dir}/raster_tiles/{image_files[i]}')
        pred = (predictor(img[...,::-1]))
        images.append({'file_name': image_files[i],
                       'width': img.shape[0],
                       'height': img.shape[0],
                       'id': i+1})
        preds.append(pred)

    # Mask postprocessing:
    if smooth_preds:
        print('Not yet implemented')
        #preds = fill_holes(preds)
        #preds = dilate_erode(preds)

    preds_coco = detectron2_mask_preds_to_coco_anns(images, preds)
    # TODO fix categories to not be hardcoded
    preds_coco['categories'] = [
        {'supercategory':'deadwood', 'id':1, 'name': 'uprightwood'},
        {'supercategory':'deadwood', 'id':2, 'name': 'groundwood'},
    ]



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
        pred_shp['to_drop'] = pred_shp.apply(lambda row: 0 if row.geometry.intersects(cell_geom) else 1, axis=1)
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

# Cell

from torchvision.models.detection.rpn import AnchorGenerator, RPNHead
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor


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


# Cell

@call_parse
def predict_segmentation(path_to_model:Param("Path to pretrained model file",type=str),
                         path_to_image:Param("Path to image to annotate", type=str),
                         outfile:Param('Path and filename for output raster', type=str),
                         processing_dir:Param("Directory to save the intermediate tiles. Deleted after use", type=str, default='temp'),
                         tile_size:Param("Tile size to use. Default 400x400px tiles", type=int, default=400),
                         tile_overlap:Param("Tile overlap to use. Default 100px", type=int, default=200),
                         use_tta:Param("Use test-time augmentation", store_true)=None
    ):
    """Segment image into land cover classes with a pretrained models
    TODO save also information about label and class
    TODO add test-time augmentations"""
    if os.path.exists(processing_dir):
        print('Processing folder exists')
        return
    os.makedirs(processing_dir)
    print(f'Reading and tiling {path_to_image} to {tile_size}x{tile_size} tiles with overlap of {tile_overlap}px')
    tiler = Tiler(outpath=processing_dir, gridsize_x=int(tile_size), gridsize_y=int(tile_size),
                  overlap=(int(tile_overlap), int(tile_overlap)))
    tiler.tile_raster(path_to_image)

    # Check whether is possible to use gpu
    cpu = True if not torch.cuda.is_available() else False

    # Loading pretrained model

    # PyTorch state dict TODO
    if path_to_model.endswith('.pth') or path_to_model.endswith('.pt'):
        print('Using PyTorch state dict not yet supported')
        print('Removing intermediate files')
        rmtree(processing_dir)
        return
    # fastai learn.export()
    elif path_to_model.endswith('.pkl'):
        learn = load_learner(path_to_model, cpu=cpu)
        test_files = get_image_files(f'{processing_dir}/raster_tiles')
        print('Starting prediction')
        os.makedirs(f'{processing_dir}/predicted_rasters')
        # Works with chunks of 300 patches
        for chunk in range(0, len(test_files), 300):
            test_dl = learn.dls.test_dl(test_files[chunk:chunk+300], num_workers=0, bs=1)
            test_dl.set_base_transforms()
            if use_tta:
                batch_tfms = [Dihedral()]
                item_tfms = [ToTensor(), IntToFloatTensor()]
                preds = learn.tta(dl=test_dl, batch_tfms=batch_tfms)[0]
            else:
                preds = learn.get_preds(dl=test_dl, with_input=False, with_decoded=False)[0]

            print('Rasterizing predictions')
            for f, p in tqdm(zip(test_files[chunk:chunk+300], preds)):
                #if len(p.shape) == 3: p = p[0]
                ds = gdal.Open(str(f))
                out_raster = gdal.GetDriverByName('gtiff').Create(f'{processing_dir}/predicted_rasters/{f.stem}.{f.suffix}',
                                                                  ds.RasterXSize,
                                                                  ds.RasterYSize,
                                                                  p.shape[0], gdal.GDT_Int16)
                out_raster.SetProjection(ds.GetProjectionRef())
                out_raster.SetGeoTransform(ds.GetGeoTransform())
                np_pred = p.numpy()#.argmax(axis=0)
                np_pred = np_pred.round(2)
                np_pred *= 100
                np_pred = np_pred.astype(np.int16)
                for c in range(p.shape[0]):
                    band = out_raster.GetRasterBand(c+1).WriteArray(np_pred[c])
                    band = None
                #band = out_raster.GetRasterBand(1).WriteArray(np_pred)
                out_raster = None
                ds = None

    print('Merging predictions')
    temp_full = f'{processing_dir}/full_raster.tif'
    untile_raster(f'{processing_dir}/predicted_rasters', outfile=temp_full, method='sum')

    print('Postprocessing predictions')

    raw_raster = gdal.Open(temp_full)
    processed_raster = gdal.GetDriverByName('gtiff').Create(outfile,
                                                            raw_raster.RasterXSize,
                                                            raw_raster.RasterYSize,
                                                            1, gdal.GDT_Int16)
    processed_raster.SetProjection(raw_raster.GetProjectionRef())
    processed_raster.SetGeoTransform(raw_raster.GetGeoTransform())
    raw_np = raw_raster.ReadAsArray()
    pred_np = raw_np.argmax(axis=0)
    band = processed_raster.GetRasterBand(1).WriteArray(pred_np)
    raw_raster = None
    band = None
    processed_raster = None

    print('Removing intermediate files')
    rmtree(processing_dir)
    return