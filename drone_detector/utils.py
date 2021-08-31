# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/00_utils.ipynb (unless otherwise specified).

__all__ = ['rangeof', 'non_max_suppression_fast', 'cone_v', 'cut_cone_v']

# Cell

from .imports import *


# Cell

def rangeof(iterable):
    "Equivalent for range(len(iterable))"
    return range(len(iterable))

# Cell

# Malisiewicz et al.
def non_max_suppression_fast(boxes, scores, overlap_thresh):
    "Right now sorts by scores, another possibility is to sort by area"

    # if there are no boxes, return an empty list
    if len(boxes) == 0:
        return []

    # if the bounding boxes integers, convert them to floats --
    # this is important since we'll be doing a bunch of divisions
    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")

    # sort prediction by scores,

    # initialize the list of picked indexes
    pick = []

    # grab the coordinates of the bounding boxes
    x1 = boxes[:,0]
    y1 = boxes[:,1]
    x2 = boxes[:,2]
    y2 = boxes[:,3]

    # compute the area of the bounding boxes and sort the bounding
    # boxes by the bottom-right y-coordinate of the bounding box
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    #idxs = np.argsort(y2)
    idxs = np.argsort(scores)

    # keep looping while some indexes still remain in the indexes
    # list
    while len(idxs) > 0:
        # grab the last index in the indexes list and add the
        # index value to the list of picked indexes
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        # find the largest (x, y) coordinates for the start of
        # the bounding box and the smallest (x, y) coordinates
        # for the end of the bounding box
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        # compute the width and height of the bounding box
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        # compute the ratio of overlap
        overlap = (w * h) / area[idxs[:last]]

        # delete all indexes from the index list that have
        idxs = np.delete(idxs, np.concatenate(([last],
                         np.where(overlap > overlap_thresh)[0])))

    # return indices for selected bounding boxes
    return pick
    #return boxes[pick].astype("int")

# Cell

def cone_v(r:float, h:float) -> float:
    "V = (Ah)/3"
    A = np.pi * r**2
    V = (A * h) / 3
    return V

def cut_cone_v(r_1:float, r_2:float, h:float):
    "V = (h(A + sqrt(A*A') + A))/3"
    A_1 = np.pi * r_1**2
    A_2 = np.pi * r_2**2
    V = (h*(A_1 + np.sqrt(A_1 * A_2) + A_2))/3
    return V
