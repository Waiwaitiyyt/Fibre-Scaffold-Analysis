import numpy as np
import cv2
import seaborn as sns
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

def fibre_result_visualise(diameter_arr: np.ndarray, img_path: str, pairs: list, edge_mask: np.ndarray, fig: Figure | None = None) -> Figure:
    if fig is None:
        fig = Figure(figsize=(12, 6))

    axes = fig.subplots(2, 3)

    ax_hist, ax_kde, ax_box = axes[0]
    ax_gray_img, ax_mask, ax_refinedContours = axes[1]

    # Titles
    ax_hist.set_title("Diameter Histogram")
    ax_kde.set_title("Kernel Density Estimation")
    ax_box.set_title("Boxplot")
    ax_gray_img.set_title("Grayscale Image")
    ax_mask.set_title("Skeleton and Measurement Sites")
    ax_refinedContours.set_title("Binary Mask")

    # Labels
    ax_hist.set_xlabel("Fibre Diameter (µm)")
    ax_kde.set_xlabel("Fibre Diameter (µm)")
    ax_box.set_xlabel("Fibre Diameter (µm)")

    # Image axes
    for ax in (ax_gray_img, ax_mask, ax_refinedContours):
        ax.axis("off")

    # Plots
    sns.histplot(diameter_arr, binwidth=3, stat="count",
                 color="lightgray", ax=ax_hist)
    sns.kdeplot(diameter_arr, color="#7092BE", lw=2, ax=ax_kde)
    sns.boxplot(x=diameter_arr, ax=ax_box)

    gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    ax_gray_img.imshow(gray_img, cmap = "gray")
    ax_mask.imshow(gray_img, cmap='gray')
    show_n = min(1000, len(pairs))
    for i in range(0, show_n, 3):
        (y1, x1), (y2, x2), dist = pairs[i]
        # color = ax_mask.cm.jet(dist / 50.0) if dist < 50 else (1, 0, 0)
        ax_mask.plot([x1, x2], [y1, y2], color='red', linewidth=1, alpha=0.6)

    ax_refinedContours.imshow(cv2.cvtColor(edge_mask, cv2.COLOR_BGR2RGB))

    fig.subplots_adjust(
        left=0.05,
        right=0.98,
        top=0.95,
        bottom=0.08,
        hspace=0.35,
        wspace=0.25
    )

    return fig

def pore_result_visualise(area_arr: np.ndarray, circularity_arr: np.ndarray, solidity_arr: np.ndarray, gray_img: np.ndarray, fig: Figure | None = None) -> Figure:
    if fig is None:
        fig = Figure(figsize=(12, 6))

    axes = fig.subplots(2, 3)

    ax_hist, ax_kde, ax_box = axes[0]
    ax_cir, ax_solidity, ax_original_img = axes[1]

    # Titles
    ax_hist.set_title("Pore Size Histogram")
    ax_kde.set_title("Kernel Density Estimation")
    ax_box.set_title("Boxplot")
    ax_original_img.set_title("Original Image")
    ax_cir.set_title("Pores Circularity")
    ax_solidity.set_title("Pores Solidity")

    # Labels
    ax_hist.set_xlabel("Pore Size (µm²)")
    ax_kde.set_xlabel("Pore Size (µm²)")
    ax_kde.ticklabel_format(style='scientific', axis='y', scilimits=(-2,2))
    ax_box.set_xlabel("Pore Size (µm²)")

    ax_original_img.axis("off")

    # Plots
    sns.histplot(area_arr, bins = "auto", stat="count",
                 color="lightgray", ax=ax_hist)
    
    sns.kdeplot(area_arr, color="#7092BE", lw=2, ax=ax_kde)
    sns.boxplot(x=area_arr, ax=ax_box)
    # Circularity kde
    sns.kdeplot(circularity_arr, color="#7092BE", lw=2, ax=ax_cir)
    # Solidity kde
    sns.kdeplot(solidity_arr, color="#7092BE", lw=2, ax=ax_solidity)

    # Original image
    ax_original_img.imshow(gray_img, cmap="gray")


    fig.subplots_adjust(
        left=0.05,
        right=0.98,
        top=0.95,
        bottom=0.08,
        hspace=0.35,
        wspace=0.25
    )

    return fig

def save_measurement_overlay(img_path: str, pairs: list, save_path: str) -> None:
    """Save the grayscale image with measurement lines as a standalone file."""
    gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(gray_img, cmap='gray') # type: ignore
    ax.axis('off')
    show_n = min(1000, len(pairs))
    for i in range(0, show_n, 3):
        (y1, x1), (y2, x2), dist = pairs[i]
        ax.plot([x1, x2], [y1, y2], color='red', linewidth=1, alpha=0.6)
    fig.savefig(save_path, bbox_inches='tight', pad_inches=0)
    plt.close(fig)