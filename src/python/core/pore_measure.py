import numpy as np
from PIL import Image
from skimage import img_as_float, exposure
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
from skimage.morphology import remove_small_objects
from skimage.measure import find_contours
from skimage.draw import polygon_perimeter
from scipy.stats import sem, gaussian_kde
from scipy.spatial import ConvexHull
from typing import Tuple


def _contour_area(pts: np.ndarray) -> float:
    """Shoelace formula. pts: (N, 2) in (x, y) order."""
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _contour_perimeter(pts: np.ndarray) -> float:
    """Sum of Euclidean distances between consecutive points (closed)."""
    diff = np.roll(pts, -1, axis=0) - pts
    return float(np.sum(np.linalg.norm(diff, axis=1)))


def _convex_hull_area(pts: np.ndarray) -> float:
    """Convex hull area via scipy. Returns 0 if hull cannot be formed."""
    if len(pts) < 3:
        return 0.0
    try:
        return ConvexHull(pts).volume  # 2-D: .volume is area
    except Exception:
        return 0.0


def ridge_enhancement(img_path: str) -> np.ndarray:
    '''
    Enhance and extract ridge featues from assigned image path and return the binary mask of ridge

    :param img_path: 
    :type img_path: str
    :return: 
    :rtype: ndarray[Any, Any]
    '''
    img = np.array(Image.open(img_path).convert("L"))
    clahe_img = exposure.equalize_adapthist(img, kernel_size=(8, 8), clip_limit=0.03)
    img_float = img_as_float(clahe_img)
    H_elems = hessian_matrix(img_float, sigma=3, order='rc', use_gaussian_derivatives=False)
    eigvals = hessian_matrix_eigvals(H_elems)
    ridge_response = np.abs(eigvals[0])
    norm = (ridge_response - ridge_response.min()) / (np.ptp(ridge_response) + 1e-6)
    mask = (norm > 0.15)
    clean_mask = remove_small_objects(mask, max_size=500).astype(np.uint8) * 255
    return clean_mask


def contour_isolate(contour: np.ndarray) -> np.ndarray:
    """contour: (N, 2) in (x, y) order, matching skimage find_contours output swapped."""
    pts = contour.reshape(-1, 2)
    x0, y0 = pts.min(axis=0).astype(int)
    x1, y1 = pts.max(axis=0).astype(int)
    h, w = (y1 - y0 + 50), (x1 - x0 + 50)
    mask = np.zeros((h, w), dtype=np.uint8)
    normalised = (25 + pts - [x0, y0]).astype(np.int32)
    # Draw closed contour perimeter
    rr, cc = polygon_perimeter(normalised[:, 1], normalised[:, 0], shape=(h, w), clip=True)
    mask[rr, cc] = 255
    return mask


def measure_contour(contour_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    '''
    Extract contours area from contour mask and return the area array 
    
    :param contour_mask: 
    :type contour_mask: np.ndarray
    :return: 
    :rtype: ndarray[Any, Any]
    '''
    # skimage find_contours returns (row, col) == (y, x); swap to (x, y) for consistency
    raw_contours = find_contours(contour_mask, level=127)

    area_list, circularity_list, solidity_list = [], [], []

    for contour in raw_contours:
        pts_xy = contour[:, ::-1]  # (y,x) -> (x,y)

        area = _contour_area(pts_xy)
        perimeter = _contour_perimeter(pts_xy)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        hull_area = _convex_hull_area(pts_xy)
        solidity = area / hull_area if hull_area > 0 else 0

        area_list.append(area)
        circularity_list.append(circularity)
        solidity_list.append(solidity)

    area_arr = np.asarray(sorted(area_list)[:-1])
    circularity_arr = np.asarray(circularity_list)
    solidity_arr = np.asarray(solidity_list)

    q_low = np.percentile(area_arr, 25)
    q_high = np.percentile(area_arr, 75)
    IQR = q_high - q_low
    lower_bound = q_low - 1.5 * IQR
    upper_bound = q_high + 1.5 * IQR
    valid_area_arr = area_arr[(area_arr >= lower_bound) & (area_arr <= upper_bound)]

    return valid_area_arr, circularity_arr, solidity_arr


def result_analyse(area_arr: np.ndarray) -> dict:
    """Return statistic result for area

    Args:
        area_arr (np.ndarray)

    Returns:
        dict
    """
    average = np.mean(area_arr)
    stdev = np.std(area_arr, ddof=1)
    kde = gaussian_kde(area_arr)
    x = np.linspace(area_arr.min(), area_arr.max(), 1000)
    y = kde(x)
    porePeak = x[np.argmax(y)]
    semValue = sem(area_arr, ddof=1)
    median = np.median(area_arr)
    quantileLow = np.quantile(area_arr, 0).astype(float)
    quantileHigh = np.quantile(area_arr, 1).astype(float)
    boot = np.random.choice(area_arr, (10000, len(area_arr)), replace=True)
    ciLow, ciHigh = np.percentile(np.median(boot, axis=1), [2.5, 97.5])

    return {
        "Average": average,
        "Standard Deviation": stdev,
        "KDE Peak": porePeak,
        "SEM": semValue,
        "median": median,
        "Q1, Q3": (quantileLow, quantileHigh),
        "IQR": quantileHigh - quantileLow,
        "95% CI": (ciLow, ciHigh),
        "Raw": area_arr.tolist()
    }


def measure(img_path: str, scale_factor: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict, np.ndarray]:
    """Perform measurement for pores

    Args:
        img_path (str): _description_
        scale_factor (float): _description_

    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray, dict, np.ndarray]: _description_
    """
    contour_mask = ridge_enhancement(img_path)
    gray_img = np.array(Image.open(img_path).convert("L"))
    area_arr_pixel, circularity_arr, solidity_arr = measure_contour(contour_mask)
    area_arr = area_arr_pixel * (scale_factor ** 2)
    pore_dict = result_analyse(area_arr)
    return area_arr, circularity_arr, solidity_arr, pore_dict, gray_img


if __name__ == "__main__":
    img_path = r"E:\CoraMetix\Fibre Diameter Measurement\sample\12.03.02_4x(3).JPG"
    area_arr, circularity_arr, solidity_arr, pore_dict, gray_img = measure(img_path, scale_factor=1.25)
    print(area_arr, len(area_arr))