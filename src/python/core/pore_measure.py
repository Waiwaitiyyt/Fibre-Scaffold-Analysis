import numpy as np
import cv2
from skimage import img_as_float # type: ignore 
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
from skimage.morphology import remove_small_objects
from scipy.stats import sem, gaussian_kde
from typing import Tuple
import matplotlib.pyplot as plt

def ridge_enhancement(img_path: str) -> np.ndarray:
    '''
    Enhance and extract ridge featues from assigned image path and return the binary mask of ridge

    :param img_path: 
    :type img_path: str
    :return: 
    :rtype: ndarray[Any, Any]
    '''
    # Apply adaptive thresholds
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    clahe = cv2.createCLAHE(clipLimit=10.0, tileGridSize=(8, 8))
    img = clahe.apply(img) # type: ignore
    img_float = img_as_float(img)
    # Enhance ridge features 
    H_elems = hessian_matrix(img_float, sigma=3, order='rc', use_gaussian_derivatives=False)
    eigvals = hessian_matrix_eigvals(H_elems)
    ridge_response = np.abs(eigvals[0])
    norm = (ridge_response - ridge_response.min()) / (np.ptp(ridge_response) + 1e-6)
    mask = (norm > 0.15)
    clean_mask = remove_small_objects(mask, max_size = 500).astype(np.uint8) * 255
    return clean_mask

def contour_isolate(contour: np.ndarray) -> np.ndarray:
    pts = contour.reshape(-1, 2)           
    x0, y0 = pts.min(axis=0).astype(int)
    x1, y1 = pts.max(axis=0).astype(int)
    h, w = (y1 - y0 + 50), (x1 - x0 + 50)
    mask = np.zeros((h, w), dtype=np.uint8)
    normalised = (25 + pts - [x0, y0]).astype(np.int32).reshape(-1, 1, 2)
    cv2.drawContours(mask, [normalised], -1, 255, 1)
    return mask

def measure_contour(contour_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    '''
    Extract contours area from contour mask and return the area array 
    
    :param contour_mask: 
    :type contour_mask: np.ndarray
    :return: 
    :rtype: ndarray[Any, Any]
    '''
    contours, _ = cv2.findContours(contour_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    area_list = []
    circularity_list = []
    solidity_list = []
    for contour in contours:
        # contour_mask = contour_isolate(contour)
        # cv2.imshow('a', contour_mask)
        # cv2.waitKey(0)
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = (4 * np.pi * area) / (perimeter ** 2)
        else:
            circularity = 0
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        area_list.append(area)
        circularity_list.append(circularity)
        solidity_list.append(solidity)
    # area_arr = np.asarray(sorted([area for area in area_list if area < 1])[:-5]).ravel()
    # circularity_arr = np.asarray(sorted(circularity_list)[:-1]).ravel()
    # solidity_arr = np.asarray(sorted(solidity_list)[:-1]).ravel()
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
    '''
    Void function for result analysis and write data into json file
    
    :param areaList:
    :type areaList: list
    '''
    average = np.mean(area_arr)
    stdev = np.std(area_arr, ddof = 1)

    kde = gaussian_kde(area_arr)
    x = np.linspace(area_arr.min(), area_arr.max(), 1000)
    y = kde(x)
    porePeak = x[np.argmax(y)]

    semValue = sem(area_arr, ddof = 1)
    median = np.median(area_arr)
    quantileLow, quantileHigh = np.quantile(area_arr, 0).astype(float), np.quantile(area_arr, 1).astype(float)
    boot = np.random.choice(area_arr, (10000, len(area_arr)), replace=True)
    ciLow, ciHigh = np.percentile(np.median(boot, axis=1), [2.5, 97.5])

    pore_dict = {"Average": average,
                 "Standard Deviation": stdev,
                 "KDE Peak": porePeak,
                 "SEM": semValue,
                 "median": median,
                 "Q1, Q3": (quantileLow, quantileHigh),
                 "IQR": quantileHigh - quantileLow,
                 "95% CI": (ciLow, ciHigh),
                 "Raw": area_arr.tolist()
                 }
    
    return pore_dict


def measure(img_path: str, scale_factor: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict, np.ndarray]:
    '''
    Perform measurement for pores
    
    :param img_path: 
    :type img_path: str
    :return: area array, circularity arrar, solidity array and the input image path for result rendering
    :rtype: Tuple[ndarray[Any, Any], ndarray[Any, Any], ndarray[Any, Any], str]
    '''
    contour_mask = ridge_enhancement(img_path)
    gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    area_arr_pixel, circularity_arr, solidity_arr = measure_contour(contour_mask)
    area_arr = area_arr_pixel * (scale_factor ** 2)
    pore_dict = result_analyse(area_arr)
    return area_arr, circularity_arr, solidity_arr, pore_dict, gray_img # type: ignore

if __name__ == "__main__":
    img_path = r"E:\CoraMetix\Fibre Diameter Measurement\sample\12.03.02_4x(3).JPG"
    area_arr, circularity_arr, solidity_arr, pore_dict, gray_img = measure(img_path, scale_factor=1.25)
    print(area_arr, len(area_arr))
