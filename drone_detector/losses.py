# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/12_losses.ipynb (unless otherwise specified).


from __future__ import print_function, division


__all__ = ['lovasz_grad', 'iou_binary', 'iou', 'isnan', 'mean', 'lovasz_hinge', 'lovasz_hinge_flat',
           'flatten_binary_scores', 'lovasz_softmax', 'lovasz_softmax_flat', 'flatten_probas', 'xloss',
           'LovaszHingeLossFlat', 'LovaszHingeLoss', 'LovaszSigmoidLossFlat', 'LovaszSigmoidLoss',
           'LovaszSoftmaxLossFlat', 'LovaszSoftmaxLoss', 'DiceLoss', 'FocalDice']

# Cell
from .imports import *
from fastai.learner import Metric
from fastai.torch_core import *
from fastai.metrics import *
from fastai.losses import BaseLoss, FocalLossFlat
from fastcore.meta import *
import sklearn.metrics as skm
import torch
import torch.nn.functional as F
from torch.autograd import Variable


# Cell

"""
Lovasz-Softmax and Jaccard hinge loss in PyTorch
Maxim Berman 2018 ESAT-PSI KU Leuven (MIT License)
"""

#nbdev_comment from __future__ import print_function, division

try:
    from itertools import  ifilterfalse
except ImportError: # py3k
    from itertools import  filterfalse as ifilterfalse


def lovasz_grad(gt_sorted):
    """
    Computes gradient of the Lovasz extension w.r.t sorted errors
    See Alg. 1 in paper
    """
    p = len(gt_sorted)
    gts = gt_sorted.sum()
    intersection = gts - gt_sorted.float().cumsum(0)
    union = gts + (1 - gt_sorted).float().cumsum(0)
    jaccard = 1. - intersection / union
    if p > 1: # cover 1-pixel case
        jaccard[1:p] = jaccard[1:p] - jaccard[0:-1]
    return jaccard


def iou_binary(preds, labels, EMPTY=1., ignore=None, per_image=True):
    """
    IoU for foreground class
    binary: 1 foreground, 0 background
    """
    if not per_image:
        preds, labels = (preds,), (labels,)
    ious = []
    for pred, label in zip(preds, labels):
        intersection = ((label == 1) & (pred == 1)).sum()
        union = ((label == 1) | ((pred == 1) & (label != ignore))).sum()
        if not union:
            iou = EMPTY
        else:
            iou = float(intersection) / float(union)
        ious.append(iou)
    iou = mean(ious)    # mean accross images if per_image
    return 100 * iou


def iou(preds, labels, C, EMPTY=1., ignore=None, per_image=False):
    """
    Array of IoU for each (non ignored) class
    """
    if not per_image:
        preds, labels = (preds,), (labels,)
    ious = []
    for pred, label in zip(preds, labels):
        iou = []
        for i in range(C):
            if i != ignore: # The ignored label is sometimes among predicted classes (ENet - CityScapes)
                intersection = ((label == i) & (pred == i)).sum()
                union = ((label == i) | ((pred == i) & (label != ignore))).sum()
                if not union:
                    iou.append(EMPTY)
                else:
                    iou.append(float(intersection) / float(union))
        ious.append(iou)
    ious = [mean(iou) for iou in zip(*ious)] # mean accross images if per_image
    return 100 * np.array(ious)


# --------------------------- HELPER FUNCTIONS ---------------------------
def isnan(x):
    return x != x


def mean(l, ignore_nan=False, empty=0):
    """
    nanmean compatible with generators.
    """
    l = iter(l)
    if ignore_nan:
        l = ifilterfalse(isnan, l)
    try:
        n = 1
        acc = next(l)
    except StopIteration:
        if empty == 'raise':
            raise ValueError('Empty mean')
        return empty
    for n, v in enumerate(l, 2):
        acc += v
    if n == 1:
        return acc
    return acc / n

def lovasz_hinge(logits, labels, per_image=True, ignore=None):
    """
    Binary Lovasz hinge loss
      logits: [B, H, W] Variable, logits at each pixel (between -\infty and +\infty)
      labels: [B, H, W] Tensor, binary ground truth masks (0 or 1)
      per_image: compute the loss per image instead of per batch
      ignore: void class id
    """
    if per_image:
        loss = mean(lovasz_hinge_flat(*flatten_binary_scores(log.unsqueeze(0), lab.unsqueeze(0), ignore))
                          for log, lab in zip(logits, labels))
    else:
        loss = lovasz_hinge_flat(*flatten_binary_scores(logits, labels, ignore))
    return loss


def lovasz_hinge_flat(logits, labels):
    """
    Binary Lovasz hinge loss
      logits: [P] Variable, logits at each prediction (between -\infty and +\infty)
      labels: [P] Tensor, binary ground truth labels (0 or 1)
      ignore: label to ignore
    """
    if len(labels) == 0:
        # only void pixels, the gradients should be 0
        return logits.sum() * 0.
    signs = 2. * labels.float() - 1.
    errors = (1. - logits * Variable(signs))
    errors_sorted, perm = torch.sort(errors, dim=0, descending=True)
    perm = perm.data
    gt_sorted = labels[perm]
    grad = lovasz_grad(gt_sorted)
    loss = torch.dot(F.relu(errors_sorted), Variable(grad))
    return loss


def flatten_binary_scores(scores, labels, ignore=None):
    """
    Flattens predictions in the batch (binary case)
    Remove labels equal to 'ignore'
    """
    scores = scores.view(-1)
    labels = labels.view(-1)
    if ignore is None:
        return scores, labels
    valid = (labels != ignore)
    vscores = scores[valid]
    vlabels = labels[valid]
    return vscores, vlabels

def lovasz_softmax(probas, labels, classes='present', per_image=False, ignore=None):
    """
    Multi-class Lovasz-Softmax loss
      probas: [B, C, H, W] Variable, class probabilities at each prediction (between 0 and 1).
              Interpreted as binary (sigmoid) output with outputs of size [B, H, W].
      labels: [B, H, W] Tensor, ground truth labels (between 0 and C - 1)
      classes: 'all' for all, 'present' for classes present in labels, or a list of classes to average.
      per_image: compute the loss per image instead of per batch
      ignore: void class labels
    """
    if per_image:
        loss = mean(lovasz_softmax_flat(*flatten_probas(prob.unsqueeze(0), lab.unsqueeze(0), ignore), classes=classes)
                          for prob, lab in zip(probas, labels))
    else:
        loss = lovasz_softmax_flat(*flatten_probas(probas, labels, ignore), classes=classes)
    return loss


def lovasz_softmax_flat(probas, labels, classes='present'):
    """
    Multi-class Lovasz-Softmax loss
      probas: [P, C] Variable, class probabilities at each prediction (between 0 and 1)
      labels: [P] Tensor, ground truth labels (between 0 and C - 1)
      classes: 'all' for all, 'present' for classes present in labels, or a list of classes to average.
    """
    if probas.numel() == 0:
        # only void pixels, the gradients should be 0
        return probas * 0.
    C = probas.size(1)
    losses = []
    class_to_sum = list(range(C)) if classes in ['all', 'present'] else classes
    for c in class_to_sum:
        fg = (labels == c).float() # foreground for class c
        if (classes == 'present' and fg.sum() == 0):
            continue
        if C == 1:
            if len(classes) > 1:
                raise ValueError('Sigmoid output possible only with 1 class')
            class_pred = probas[:, 0]
        else:
            class_pred = probas[:, c]
        errors = (Variable(fg) - class_pred).abs()
        errors_sorted, perm = torch.sort(errors, 0, descending=True)
        perm = perm.data
        fg_sorted = fg[perm]
        losses.append(torch.dot(errors_sorted, Variable(lovasz_grad(fg_sorted))))
    return mean(losses)


def flatten_probas(probas, labels, ignore=None):
    """
    Flattens predictions in the batch
    """
    if probas.dim() == 3:
        # assumes output of a sigmoid layer
        B, H, W = probas.size()
        probas = probas.view(B, 1, H, W)
    B, C, H, W = probas.size()
    probas = probas.permute(0, 2, 3, 1).contiguous().view(-1, C)  # B * H * W, C = P, C
    labels = labels.view(-1)
    if ignore is None:
        return probas, labels
    valid = (labels != ignore)
    vprobas = probas[valid.nonzero().squeeze()]
    vlabels = labels[valid]
    return vprobas, vlabels

def xloss(logits, labels, ignore=None):
    """
    Cross entropy loss
    """
    return F.cross_entropy(logits, Variable(labels), ignore_index=255)

# Cell

class LovaszHingeLossFlat(BaseLoss):
    "Same as `LovaszHingeLoss` but flattens input and target"
    y_int = True
    @use_kwargs_dict(keep=True, ignore=None)
    def __init__(self, *args, axis=-1, **kwargs): super().__init__(LovaszHingeLoss, *args, axis=axis, is_2d=False, **kwargs)
    def decodes(self, x): return x>0
    def activation(self, x): return x


class LovaszHingeLoss(Module):
    """
    Lovasz-Hinge loss from https://arxiv.org/abs/1705.08790, with per_image=True

    Todo

    Binary Lovasz hinge loss
      logits: [P] Variable, logits at each prediction (between -\infty and +\infty)
      labels: [P] Tensor, binary ground truth labels (0 or 1)
      ignore: label to ignore
    """

    def __init__(self, ignore=None):
        store_attr()

    def forward(self, outputs, targets):
        if self.ignore is not None:
            valid = (targets != self.ignore)
            outputs = outputs[valid]
            targets = targets[valid]
        if len(targets) == 0:
            # only void pixels, the gradiens should be 0
            return outputs.sum() * 0.
        signs = 2. * targets.float() - 1.
        errors = (1. - outputs * Variable(signs))
        errors_sorted, perm = torch.sort(errors, dim=0, descending=True)
        perm = perm.data
        gt_sorted = targets[perm]
        grad = lovasz_grad(gt_sorted)
        loss = torch.dot(F.relu(errors_sorted), Variable(grad))
        return loss

    def decodes(self, x): x>0
    def activation(self,x): return x

# Cell

class LovaszSigmoidLossFlat(BaseLoss):
    "Same as `LovaszSigmoidLoss` but flattens input and target"
    y_int = True
    @use_kwargs_dict(keep=True, ignore=None)
    def __init__(self, *args, axis=-1, **kwargs): super().__init__(LovaszSigmoidLoss, *args, axis=axis, is_2d=False, **kwargs)
    def decodes(self, x): return x>0
    def activation(self, x): return x

class LovaszSigmoidLoss(Module):
    """
    Lovasz-Sigmoid loss from https://arxiv.org/abs/1705.08790, with per_image=False

    Todo

      probas: [P, C] Variable, logits at each prediction (between -\infty and +\infty)
      labels: [P] Tensor, binary ground truth labels (0 or 1)
      ignore: label to ignore
    """

    def __init__(self, ignore=None):
        store_attr()

    def forward(self, outputs, targets):
        if self.ignore is not None:
            valid = (targets != self.ignore)
            outputs = outputs[valid]
            targets = targets[valid]
        if len(targets) == 0:
            # only void pixels, the gradiens should be 0
            return outputs.sum() * 0.
        outputs = torch.sigmoid(outputs)
        fg = (targets == 1).float() # foregroud pixels
        errors = (Variable(fg) - outputs).abs()
        errors_sorted, perm = torch.sort(errors, 0, descending=True)
        perm = perm.data
        fg_sorted = fg[perm]
        loss = torch.dot(errors_sorted, Variable(lovasz_grad(fg_sorted)))
        return loss

    def decodes(self, x): return x>0.5
    def activation(self, x): return torch.sigmoid(x)

# Cell

class LovaszSoftmaxLossFlat(BaseLoss):
    "Same as `LovaszSigmoidLoss` but flattens input and target"
    y_int = True
    @use_kwargs_dict(keep=True, classes='present', ignore=None)
    def __init__(self, *args, axis=1, **kwargs): super().__init__(LovaszSoftmaxLoss, *args, axis=axis, is_2d=True,
                                                                   flatten=True,**kwargs)
    def activation(self, out): return F.softmax(out, dim=self.axis)
    def decodes(self, out): return out.argmax(dim=self.axis)


class LovaszSoftmaxLoss(Module):
    """
    Lovasz-Sigmoid loss from https://arxiv.org/abs/1705.08790, with per_image=False

    """
    def __init__(self, classes='present', ignore=None):
        store_attr()

    def forward(self, outputs, targets):
        if self.ignore is not None:
            valid = (targets != self.ignore)
            outputs = outputs[valid]
            targets = targets[valid]
        if outputs.numel() == 0:
            # only void pixels, the gradients should be 0
            return outputs * 0.
        outputs = F.softmax(outputs, dim=-1)
        C = outputs.size(1)
        losses = []
        class_to_sum = list(range(C)) if self.classes in ['all', 'present'] else self.classes
        for c in class_to_sum:
            fg = (targets == c).float() # foreground for class c
            if (self.classes == 'present' and fg.sum() == 0):
                continue
            if C == 1:
                if len(self.classes) > 1:
                    raise ValueError('Sigmoid output possible only with 1 class')
                class_pred = outputs[:, 0]
            else:
                class_pred = outputs[:, c]
            errors = (Variable(fg) - class_pred).abs()
            errors_sorted, perm = torch.sort(errors, 0, descending=True)
            perm = perm.data
            fg_sorted = fg[perm]
            losses.append(torch.dot(errors_sorted, Variable(lovasz_grad(fg_sorted))))
        return mean(losses)

    def activation(self, out): return F.softmax(out, dim=-1)
    def decodes(self, out): return out.argmax(dim=-1)

# Cell

class DiceLoss:
    "Dice loss for segmentation. Already part of fastai 2.4 but due to icevision combatibilities copypasted here"
    def __init__(self, axis=1, smooth=1):
        store_attr()
    def __call__(self, pred, targ):
        targ = self._one_hot(targ, pred.shape[self.axis])
        pred, targ = flatten_check(self.activation(pred), targ)
        inter = (pred*targ).sum()
        union = (pred+targ).sum()
        return 1 - (2. * inter + self.smooth)/(union + self.smooth)
    @staticmethod
    def _one_hot(x, classes, axis=1):
        "Creates one binay mask per class"
        return torch.stack([torch.where(x==c, 1, 0) for c in range(classes)], axis=axis)
    def activation(self, x): return F.softmax(x, dim=self.axis)
    def decodes(self, x):    return x.argmax(dim=self.axis)

# Cell

class FocalDice:
    "Dice and Focal combined"
    def __init__(self, axis=1, smooth=1., alpha=1.):
        store_attr()
        self.focal_loss = FocalLossFlat(axis=axis)
        self.dice_loss =  DiceLoss(axis, smooth)

    def __call__(self, pred, targ):
        return self.focal_loss(pred, targ) + self.alpha * self.dice_loss(pred, targ)

    def decodes(self, x):    return x.argmax(dim=self.axis)
    def activation(self, x): return F.softmax(x, dim=self.axis)