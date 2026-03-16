import numpy as np
import cv2
from skimage import img_as_float # type: ignore 
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
from skimage.morphology import remove_small_objects
from skimage.measure import label
from scipy.stats import sem, gaussian_kde
from typing import List, Tuple
import json

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
    mask = (norm > 0.15).astype(np.uint8) * 255
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
    area_arr = np.asarray(sorted([area for area in area_list if area < 1])[:-5]).ravel()
    circularity_arr = np.asarray(sorted(circularity_list)[:-1]).ravel()
    solidity_arr = np.asarray(sorted(solidity_list)[:-1]).ravel()

    return area_arr, circularity_arr, solidity_arr
    


def resultAnalyse(area_arr: np.ndarray) -> None:
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

    with open("data.json", "r") as jsonFile:
        data = json.load(jsonFile)

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

    data["Pores Param"] = pore_dict
    with open("data.json", "w") as jsonFile:
        json.dump(data, jsonFile, indent = 2)


def measure(img_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    '''
    Perform measurement for pores
    
    :param img_path: 
    :type img_path: str
    :return: area array, circularity arrar, solidity array and the input image path for result rendering
    :rtype: Tuple[ndarray[Any, Any], ndarray[Any, Any], ndarray[Any, Any], str]
    '''
    contour_mask = ridge_enhancement(img_path)
    area_arr_pixel, circularity_arr, solidity_arr = measure_contour(contour_mask)
    with open("data.json", "r") as jsonFile:
        data = json.load(jsonFile)
    scaleFactor = data["scaleFactor"]
    area_arr = area_arr_pixel * (scaleFactor ** 2)
    resultAnalyse(area_arr)
    return area_arr, circularity_arr, solidity_arr, img_path

   
