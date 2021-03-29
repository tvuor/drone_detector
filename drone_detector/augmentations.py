# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/09_augmentations.ipynb (unless otherwise specified).

__all__ = ['AlbumentationsTransform', 'SegmentationAlbumentationsTransform', 'segmentation_aug_tfms_fastai']

# Cell

from fastai.vision.all import *
import albumentations as A
from icevision.all import *
from .data import *

# Cell

class AlbumentationsTransform(RandTransform):
    "A transform handler for multiple `Albumentation` transforms in simple classification or regression tasks."
    split_idx, order = None, 2

    def __init__(self, train_aug, valid_aug=None): store_attr()

    def before_call(self, b, split_idx): self.idx = split_idx

    def encodes(self, img:PILImage):
        if self.idx == 0:
            aug_img = self.train_aug(image=np.array(img))['image']
        else:
            if valid_aug is None: aug_img = self.valid_aug(image=np.array(img))['image']
            else: return aug_img
        return PILImage.create(aug_img)

    def encodes(self, img:MultiChannelTensorImage):
        if self.idx == 0:
            aug_img = self.train_aug(image=np.array(img).transpose(1,2,0))['image'].transpose(2,0,1)
        else:
            if valid_aug is not None: aug_img = self.valid_aug(image=np.array(img).transpose(1,2,0))['image'].transpose(2,0,1)
            else: return aug_img
        return MultiChannelTensorImage.create(aug_img)


# Cell

class SegmentationAlbumentationsTransform(ItemTransform):
    "A transform handler for `Albumentation` transforms for segmentation tasks."
    split_idx = 0

    def __init__(self, aug): store_attr()

    def encodes(self, x):
        "Because TypeDispatch doesn't work on tuple with specific types we need to do this"
        img, mask = x
        if isinstance(img, PILImage) and isinstance(mask, PILMask):
            aug = self.aug(image=np.array(img), mask=np.array(mask))
            return PILImage.create(aug['image']), PILMask.create(aug['mask'])

        elif isinstance(img, PILImage) and isinstance(mask, RegressionMask):
            aug = self.aug(image=np.array(img), mask=np.array(mask))
            return PILImage.create(aug['image']), RegressionMask.create(aug['mask'])

        elif isinstance(img, MultiChannelTensorImage) and isinstance(mask, PILMask):
            img = np.array(img).transpose(1, 2, 0)
            aug = self.aug(image=img, mask=np.array(mask))
            return (MultiChannelTensorImage.create(aug['image'].transpose(2,0,1)),
                    PILMask.create(aug['mask']))

        elif isinstance(img, MultiChannelTensorImage) and isinstance(mask, RegressionMask):
            img = np.array(img).transpose(1,2,0)
            aug = self.aug(image=img, mask=np.array(mask))
            return (MultiChannelTensorImage.create(aug['image'].transpose(2,0,1)),
                    RegressionMask.create(aug['mask']))

        elif isinstance(img, MultiChannelTensorImageTuple) and isinstance(mask, PILMask):
            n_imgs = len(img)
            img = np.array(torch.cat(img)).transpose(1, 2, 0)
            aug = self.aug(image=img, mask=np.array(mask))
            return (MultiChannelTensorImageTuple.create(np.split(aug['image'].transpose(2,0,1), n_imgs)),
                    PILMask.create(aug['mask']))

        elif isinstance(img, MultiChannelTensorImageTuple) and isinstance(mask, RegressionMask):
            n_imgs = len(img)
            img = np.array(torch.cat(img)).transpose(1, 2, 0)
            aug = self.aug(image=img, mask=np.array(mask))
            return (MultiChannelTensorImageTuple.create(np.split(aug['image'].transpose(2,0,1), n_imgs)),
                    RegressionMask.create(aug['mask']))

        else: return x

# Cell

def segmentation_aug_tfms_fastai(size=160):
    "Utilize `tfms.A.aug_tfms` with fastai and SegmentationDataloaders"
    return SegmentationAlbumentationsTransform(A.Compose(tfms.A.aug_tfms(size=size, crop_fn=tfms.A.RandomCrop)))
