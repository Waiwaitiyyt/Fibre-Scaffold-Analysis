import json
from tkinter import filedialog


def _load_json() -> dict:
    with open("config.json", "r") as f:
        return json.load(f)


def _save_json(data: dict) -> None:
    with open("config.json", "w") as f:
        json.dump(data, f, indent=2)


def selectImg():
    filetypes = [
        ("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif"),
        ("PNG Files", "*.png"),
        ("JPEG Files", "*.jpg *.jpeg"),
    ]
    filename = filedialog.askopenfilename(
        title="Open a file",
        initialdir="/",
        filetypes=filetypes,
    )
    if filename:
        data = _load_json()
        data["img_path"] = filename
        _save_json(data)


def saveResultImg():
    pass


if __name__ == "__main__":
    pass
