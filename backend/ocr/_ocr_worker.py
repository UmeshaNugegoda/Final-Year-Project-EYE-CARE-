"""
Standalone EasyOCR worker process.

Called by reader.py as a subprocess:
    python _ocr_worker.py <image_path>

Loads EasyOCR, runs readtext on the image, prints JSON to stdout, then exits.
All ~1.5 GB of PyTorch weights are released when the process exits, preventing
memory accumulation across consecutive Flask requests.

Output format: JSON array of [[[x,y],...], text, confidence] per detected region.
"""
import sys
import json


def main():
    if len(sys.argv) < 2:
        print(json.dumps([]))
        return

    image_path = sys.argv[1]

    import easyocr
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = reader.readtext(image_path, detail=1)

    # Convert numpy types to plain Python so json.dumps works
    serialisable = []
    for bbox, text, conf in results:
        serialisable.append([
            [[float(x), float(y)] for x, y in bbox],
            str(text),
            float(conf),
        ])

    print(json.dumps(serialisable))


if __name__ == "__main__":
    main()
