"""
A solution module based on widths between pair-edges of the fibre.
The core pipeline is: Bresenham iteration on normal direction + 8-domain detection + hardcode for minimum distance threshold

Author: waiwaiti
Date: 2026-02-08

"""
import cv2
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import sem, gaussian_kde
from skimage.morphology import skeletonize, medial_axis, remove_small_objects
from skimage import img_as_float # type: ignore
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
from scipy.ndimage import distance_transform_edt
try:
    import measure_tool # type: ignore
except:
    pass
import warnings
from typing import Tuple
warnings.filterwarnings('ignore')

def ridge_enhancement(img_path: str, sigma: int = 2, threshold: float = 0.15) -> np.ndarray:
    '''
    Enhance and extract ridge featues from assigned image path and return the binary mask of ridge

    :param img_path: 
    :type img_path: str
    :param sigma: 
    :type sigma: int
    :param threshold: 
    :type threshold: float
    :return: 
    :rtype: ndarray[Any, Any]
    '''
    # Apply adaptive thresholds
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    clahe = cv2.createCLAHE(clipLimit=10.0, tileGridSize=(8, 8))
    img = clahe.apply(img) # type: ignore
    img_float = img_as_float(img)
    # Enhance ridge features 
    H_elems = hessian_matrix(img_float, sigma=sigma, order='rc', use_gaussian_derivatives=False)
    eigvals = hessian_matrix_eigvals(H_elems)
    ridge_response = np.abs(eigvals[0])
    norm = (ridge_response - ridge_response.min()) / (np.ptp(ridge_response) + 1e-6)
    mask = (norm > threshold).astype(np.uint8) * 255
    return mask

def exclude_junction(skeleton_mask: np.ndarray, jer: float) -> np.ndarray:
    '''
    Exclude the part near intersection and crossing part of skeleton mask for more accurate measurement
    
    :param skeleton_mask:
    :type skeleton_mask: np.ndarray
    :param jer: Junction Exclusion Radius (JER), controls the distance from junction
    :type jer: float
    :return: The skeleton mask with the junction and intersection part removed
    :rtype: ndarray[Any, Any]
    '''
    padded = np.pad(skeleton_mask.astype(np.uint8), 1)
    neighbor_counts = np.zeros_like(skeleton_mask, dtype=np.int32)
    offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    for dy, dx in offsets:
        neighbor_counts += padded[1+dy:1+dy+skeleton_mask.shape[0],
                                  1+dx:1+dx+skeleton_mask.shape[1]]

    junction_mask = skeleton_mask & (neighbor_counts >= 3)

    # --- Junction exclusion zone ---
    if junction_mask.any():
        junc_map = np.zeros_like(skeleton_mask, dtype=np.uint8)
        junc_map[junction_mask] = 1
        dist_to_junc = distance_transform_edt(1 - junc_map)
        junction_exclusion_radius = jer 
        near_junction = dist_to_junc <= junction_exclusion_radius # type: ignore
    else:
        near_junction = np.zeros_like(skeleton_mask, dtype=bool)

    keep_mask = skeleton_mask & (neighbor_counts == 2) & (~near_junction)

    return keep_mask

def edge_width(ridge_mask: np.ndarray) -> float:
    '''
    Calulate the average width of ridge in mask. Needed to be combined with the internal fibre width for complete fibre diameter
    
    :param ridge_mask: 
    :type ridge_mask: np.ndarray
    :return: 
    :rtype: float
    '''
    centerline, distance_map = medial_axis(ridge_mask, return_distance=True)
    diameters = distance_map * 2
    refined_centerline = exclude_junction(centerline, 20)
    diameter_values = diameters[refined_centerline]
    return np.mean(diameter_values) - 2 # 2 here, is minused due to the hessian matrix selection which includes 2 extra px at the boundary

def bresenham_line(y0, x0, y1, x1) -> list:
    '''
    Returns all pixels along a line via Bresenham's algorithm
    
    :param y0: 
    :param x0: 
    :param y1: 
    :param x1: 
    :return: 
    :rtype: list
    '''
    points = []
    
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    x, y = x0, y0
    
    while True:
        points.append((y, x))
        
        if x == x1 and y == y1:
            break
        
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    
    return points

def local_pca_normal(skeleton: np.ndarray, y: int, x: int, window_size: int = 15) -> Tuple[float, float]:
    """
    Calculate the local unit normal vector by applying local PCA approximation
    
    Workflow:
    1. Extract all points around the sampling point inside a window area
    2. Execute PCA and obtain tangent vector
    3. Obtain normal vector via tangent vector
    
    
    :param skeleton: np.ndarray
    :param y: int
    :param x: int
    :param window_size: int
    
    :return: 
    :rtype: float, float
    """
    h, w = skeleton.shape
    
    y_min = max(0, y - window_size)
    y_max = min(h, y + window_size + 1)
    x_min = max(0, x - window_size)
    x_max = min(w, x + window_size + 1)
    
    window = skeleton[y_min:y_max, x_min:x_max]
    local_coords = np.argwhere(window)
    
    if len(local_coords) < 3:
        return 0.0, 0.0
    
    local_coords[:, 0] += y_min
    local_coords[:, 1] += x_min

    distances = np.sqrt((local_coords[:, 0] - y)**2 + (local_coords[:, 1] - x)**2)
    mask = distances <= window_size
    local_coords = local_coords[mask]
    
    if len(local_coords) < 3:
        return 0.0, 0.0
    

    mean_y = local_coords[:, 0].mean()
    mean_x = local_coords[:, 1].mean()
    centered = local_coords - np.array([mean_y, mean_x])
    cov_matrix = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
    tangent = eigenvectors[:, -1]  # [dy, dx]

    normal = np.array([-tangent[1], tangent[0]])
    norm = np.linalg.norm(normal)
    if norm > 1e-8:
        normal = normal / norm
    else:
        return 0.0, 0.0
    
    return float(normal[0]), float(normal[1])  # (ny, nx)



def measure_edge_pair_distances_final(edge_mask: np.ndarray, 
                                       sample_rate: float = 0.2,
                                       max_search_distance: int = 50,
                                       min_distance_hard: int = 5,
                                       jer: int = 40) -> Tuple[list, np.ndarray]:
    '''
    A comprehensive solution for measuring distance between curve pairs.
    The algorithm pipeline:
    1. Calculate tangent and normal vector for sampling direction
    2. Apply Bresenham's algorithm iterate through pixels with minimum and maximum sampling thresholds
    3. Apply 8-pixel-domain for sampling to detect intersection with line-pairs
    
    :param edge_mask: Mask for centreline 
    :type edge_mask: np.ndarray

    :param sample_rate: Ratio of sampling relative to entire point set for balance of accuracy and computation \n
            - 0.1 = quick search
            - 0.5 = balance
            - 1.0 = completed search
    :type sample_rate: float

    :param max_search_distance: Maximum sampling distance along normal direction, 1.5-2x of expected diameter would be recommended
    :type max_search_distance: int

    :param min_distance_hard: Minimum distance for starting sampling in order to avoid error 
    :type min_distance_hard: int

    :param jer: Junction exclusion radius
    :type jer: int

    :param smooth_sigma: Smoothing factor
    :type smooth_sigma: float
    
    :return: 
        edge_pairs : list of tuples [(coord1, coord2, distance), ...] \n
        distances : ndarray, paring distances \n
    :rtype: Tuple[list[Any], ndarray[Any, Any]
    '''

    # Skeleton Extraction and refining
    raw_skeleton = skeletonize(edge_mask)
    skeleton = exclude_junction(raw_skeleton, jer)
    skeleton = remove_small_objects(skeleton, min_size = 10, connectivity = 2)
    edge_coords = np.argwhere(skeleton)
    
    if len(edge_coords) == 0:
        return [], np.array([])
    
    
    # Sampling
    n_total = len(edge_coords)
    n_sample = int(n_total * sample_rate)
    sample_indices = np.random.choice(n_total, min(n_sample, n_total), replace=False)
    
    def has_edge_in_4neighbors(y, x):
        h, w = skeleton.shape
        for dy, dx in [(-1, 0), (1, 0), (0, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                if skeleton[ny, nx]:
                    return True
        return False
    

    # Points iteration sampling
    edge_pairs = []
    distances = []
    h, w = skeleton.shape
    for idx in sample_indices:
        y0, x0 = edge_coords[idx]
        ny, nx = local_pca_normal(skeleton, y0, x0)
        # ny, nx = normal_y[y0, x0], normal_x[y0, x0]
        if abs(ny) < 0.1 and abs(nx) < 0.1:
            continue
        candidates = []

        for direction in [1, -1]:
            end_y = int(y0 + direction * ny * max_search_distance)
            end_x = int(x0 + direction * nx * max_search_distance)
            end_y = max(0, min(h-1, end_y))
            end_x = max(0, min(w-1, end_x))
            try:
                line_points = measure_tool.bresenham_line(y0, x0, end_y, end_x)
            except:
                line_points = bresenham_line(y0, x0, end_y, end_x)
            for i, (py, px) in enumerate(line_points):
                if i < min_distance_hard:
                    continue
                if i >= max_search_distance:
                    break
                if has_edge_in_4neighbors(py, px):
                    dist = np.sqrt((py - y0)**2 + (px - x0)**2)
                    if dist > min_distance_hard * np.sqrt(2):
                        candidates.append(((py, px), dist))
                    break
        
        # Result filtration
        # Reject when have two results
        if len(candidates) == 0:
            continue
        elif len(candidates) == 1:
            paired_coord, dist = candidates[0]
        else:
            continue
        
        edge_pairs.append(((y0, x0), paired_coord, dist))
        distances.append(dist)
    average_ridge_width = edge_width(edge_mask)
    distances = np.array(distances)
    distances += average_ridge_width

    # plt.figure()
    # plt.imshow(skeleton, cmap='gray') # type: ignore
    # show_n = min(1000, len(edge_pairs))
    # for i in range(0, show_n, 3):
    #     (y1, x1), (y2, x2), dist = edge_pairs[i]
    #     color = plt.cm.jet(dist / 50.0) if dist < 50 else (1, 0, 0) # type: ignore
    #     plt.plot([x1, x2], [y1, y2], color=color, linewidth=1, alpha=0.6)
    # plt.show()
    return edge_pairs, distances

def result_analyse(diameter_arr: np.ndarray) -> dict:
    '''
    Return the analysis result
    
    :param diameterList:
    :type diameterList: list
    '''
    average = np.mean(diameter_arr)
    stdev = np.std(diameter_arr, ddof = 1)

    kde = gaussian_kde(diameter_arr)
    x = np.linspace(diameter_arr.min(), diameter_arr.max(), 1000)
    y = kde(x)
    fibrePeak = x[np.argmax(y)]

    semValue = sem(diameter_arr, ddof = 1)
    median = np.median(diameter_arr)
    quantileLow, quantileHigh = np.quantile(diameter_arr, 0).astype(float), np.quantile(diameter_arr, 1).astype(float)
    boot = np.random.choice(diameter_arr, (10000, len(diameter_arr)), replace=True)
    ciLow, ciHigh = np.percentile(np.median(boot, axis=1), [2.5, 97.5])

    fibre_dict = {"Average": average,
                 "Standard Deviation": stdev,
                 "KDE Peak": fibrePeak,
                 "SEM": semValue,
                 "median": median,
                 "Q1, Q3": (quantileLow, quantileHigh),
                 "IQR": quantileHigh - quantileLow,
                 "95% CI": (ciLow, ciHigh),
                 "Raw": diameter_arr.tolist()
                 }
    
    return fibre_dict



def measure(img_path: str, 
            sample_rate: float = 0.5, 
            max_search_distance: int = 50, 
            min_distance_hard: int= 5, 
            jer: int = 40, 
            scale_factor: float = 1.25, 
            sigma: int = 2, 
            threshold: float = 0.15) -> Tuple[np.ndarray, list, np.ndarray, dict]:
    '''
    Perform measurement for fibres
    
    :param img_path:
    :type img_path: str

    :param sample_rate: Ratio of sampling relative to entire point set for balance of accuracy and computation \n
            - 0.1 = quick search
            - 0.5 = balance
            - 1.0 = completed search
    :type sample_rate: float

    :param max_search_distance: Maximum sampling distance along normal direction, 1.5-2x of expected diameter would be recommended
    :type max_search_distance: int

    :param min_distance_hard: Minimum distance for starting sampling in order to avoid error 
    :type min_distance_hard: int

    :param jer: Junction exclusion radius
    :type jer: int

    :param smooth_sigma: Smoothing factor
    :type smooth_sigma: float

    :param scale_factor: Scale factor
    :type scale_factor: float

    :return: True diameter array, point pairs and ridge mask
    :rtype: Tuple[ndarray[Any, Any], list[Any], ndarray[Any, Any]]
    '''
    edge_mask = ridge_enhancement(img_path, sigma, threshold)
    pairs, distances = measure_edge_pair_distances_final(edge_mask, sample_rate, max_search_distance, min_distance_hard, jer)
    distances *= scale_factor
    fibre_dict = result_analyse(distances)
    return distances, pairs, edge_mask, fibre_dict


if __name__ == "__main__":
    img_path = r"C:\Users\EnDes\Desktop\Untitled.png"
    distances, pairs, edge_mask, fibre_dict = measure(img_path, jer = 50)
    print(np.mean(distances))

    gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)


    plt.figure()
    plt.imshow(gray_img, cmap='gray') # type: ignore
    show_n = min(1000, len(pairs))
    for i in range(0, show_n, 3):
        (y1, x1), (y2, x2), dist = pairs[i]
        color = plt.cm.jet(dist / 50.0) if dist < 50 else (1, 0, 0) # type: ignore
        plt.plot([x1, x2], [y1, y2], color=color, linewidth=1, alpha=0.6)
    plt.show()
