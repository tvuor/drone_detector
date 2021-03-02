# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_visualizations.ipynb (unless otherwise specified).

__all__ = ['show_im_mask_pred', 'plot_grid_preds_actuals_raws', 'show_raw_mask_pred']

# Cell

from icevision.all import *
from fastcore.dispatch import *
from fastai.data.all import *
from fastai.vision.all import *

# Cell

@typedispatch
def show_results(x:TensorImage, y:TensorMask, samples, outs, ctxs, max_n=6,
                 nrows=None, ncols=3, figsize=None, **kwargs):
    "Patch `show_results` to show segmentation results in three columns (no-mask, ground truth, prediction)"
    if ctxs is None: ctxs = get_grid(min(len(samples), max_n), nrows=nrows, ncols=ncols, add_vert=1, figsize=figsize,
                                     double=False, title='Image/Target/Prediction')

    for i in range(2):
        ctxs[::3] = [b.show(ctx=c, **kwargs) for b,c,_ in zip(samples.itemgot(0), ctxs[::3],range(3*max_n))]
        ctxs[1::3] = [b.show(ctx=c, **kwargs) for b,c,_ in zip(samples.itemgot(i), ctxs[1::3],range(2*max_n))]

    for o in [samples,outs]:
        ctxs[2::3] = [b.show(ctx=c, **kwargs) for b,c,_ in zip(o.itemgot(0),ctxs[2::3], range(2*max_n))]

    return ctxs

# Cell

def show_im_mask_pred(preds, max_n=4):
    """
    Preds is a list of predictions acquired with `learn.get_preds(with_input=True, with_decoded=True)
    Should probably work like `learn.show_results` instead of this?
    """
    ims = preds[0]
    masks = preds[2]
    preds = preds[3]
    idxs = np.random.randint(0, len(ims), max_n)
    fig, axs = plt.subplots(max_n, 3, figsize=(12, max_n*4+1))
    plt.suptitle('Image/Ground truth/prediction')
    for a in axs.flatten():
        a.set_xticks([])
        a.set_yticks([])
    for i in range(max_n):
        tempim = ims[idxs[i]].cpu().numpy().copy()
        tempim = np.moveaxis(tempim, 0, 2)
        tempim *= IMAGENET_STATS[1]
        tempim += IMAGENET_STATS[0]
        axs[i,0].imshow(tempim)
        tempmask = masks[idxs[i]].cpu().numpy().copy()
        tempmask = np.ma.masked_where(tempmask == 0, tempmask)
        axs[i,1].imshow(tempim)
        axs[i,1].imshow(tempmask, alpha=0.5, cmap='viridis_r')
        temppred = preds[idxs[i]].cpu().numpy().copy()
        temppred = np.ma.masked_where(temppred == 0, temppred)
        axs[i,2].imshow(tempim)
        axs[i,2].imshow(temppred, alpha=0.5, cmap='viridis_r')
    plt.tight_layout()
    return

# Cell

def plot_grid_preds_actuals_raws(
    raws, actuals, predictions, figsize=None, show=False, annotations=None, **kwargs
):
    fig, axs = plt.subplots(
        nrows=len(actuals),
        ncols=3,
        figsize=figsize or (6, 6 * len(actuals) / 2 / 0.75),
        **kwargs,
    )
    i = 0
    for im, ax in zip(zip(raws, actuals, predictions), axs.reshape(-1, 3)):
        ax[0].imshow(im[0])
        ax[0].set_title('Aerial image')
        ax[1].imshow(im[1], cmap=None)
        ax[1].set_title("Expert annotations")
        ax[2].imshow(im[2], cmap=None)
        ax[2].set_title("Predicted annotations")

        if annotations is None:
            ax[0].set_axis_off()
            ax[1].set_axis_off()
            ax[2].set_axis_off()
        else:
            ax[0].set_axis_off()
            ax[1].get_xaxis().set_ticks([])
            ax[1].set_frame_on(False)
            ax[1].get_yaxis().set_visible(False)
            ax[1].set_xlabel(annotations[i][0], ma="left")

            ax[2].get_xaxis().set_ticks([])
            ax[2].set_frame_on(False)
            ax[2].get_yaxis().set_visible(False)
            ax[2].set_xlabel(annotations[i][1], ma="left")

            i += 1

    plt.tight_layout()
    if show:
        plt.show()
    return axs

def show_raw_mask_pred(
    samples: Union[Sequence[np.ndarray], Sequence[dict]],
    preds: Sequence[dict],
    class_map: Optional[ClassMap] = None,
    denormalize_fn: Optional[callable] = denormalize_imagenet,
    display_label: bool = True,
    display_bbox: bool = True,
    display_mask: bool = True,
    ncols: int = 1,
    figsize=None,
    show=False,
    annotations=None,
) -> None:

    if not len(samples) == len(preds):
        raise ValueError(
            f"Number of imgs ({len(samples)}) should be the same as "
            f"the number of preds ({len(preds)})"
        )

    if all(type(x) is dict for x in samples):
        raws = [
            draw_sample(
                sample=sample,
                class_map=class_map,
                display_label=False,
                display_bbox=False,
                display_mask=False,
                denormalize_fn=denormalize_fn,
            )
            for sample in samples
        ]
        actuals = [
            draw_sample(
                sample=sample,
                class_map=class_map,
                display_label=display_label,
                display_bbox=display_bbox,
                display_mask=display_mask,
                denormalize_fn=denormalize_fn,
            )
            for sample in samples
        ]

        imgs = [sample["img"] for sample in samples]
        predictions = [
            draw_pred(
                img=img,
                pred=pred,
                class_map=class_map,
                denormalize_fn=denormalize_fn,
                display_label=display_label,
                display_bbox=display_bbox,
                display_mask=display_mask,
            )
            for img, pred in zip(imgs, preds)
        ]

        plot_grid_preds_actuals_raws(
            raws, actuals, predictions, figsize=figsize, show=show, annotations=annotations
        )

    else:
        partials = [
            partial(
                show_pred,
                img=img,
                pred=pred,
                class_map=class_map,
                denormalize_fn=denormalize_fn,
                display_label=display_label,
                display_bbox=display_bbox,
                display_mask=display_mask,
                show=False,
            )
            for img, pred in zip(samples, preds)
        ]
        plot_grid(
            partials, ncols=ncols, figsize=figsize, show=show, annotations=annotations
        )