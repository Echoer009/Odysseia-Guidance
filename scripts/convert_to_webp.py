import os
from PIL import Image


def convert_images_to_webp(root_dir):
    """
    Recursively finds all PNG images in a directory and converts them to WebP format,
    preserving transparency.

    Args:
        root_dir (str): The root directory to start searching from.
    """
    print(f"Starting image conversion in directory: {root_dir}")
    converted_count = 0
    skipped_count = 0

    for subdir, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".png"):
                png_path = os.path.join(subdir, file)
                webp_path = os.path.splitext(png_path)[0] + ".webp"

                if os.path.exists(webp_path) and os.path.getmtime(
                    webp_path
                ) > os.path.getmtime(png_path):
                    skipped_count += 1
                    continue

                try:
                    with Image.open(png_path) as img:
                        # Save as WebP, preserving transparency.
                        # Pillow handles RGBA conversion automatically.
                        img.save(webp_path, "webp", quality=85, lossless=True)
                        print(f"Successfully converted '{png_path}' to '{webp_path}'")
                        converted_count += 1
                except Exception as e:
                    print(f"Error converting file {png_path}: {e}")

    print("\n--- Conversion Summary ---")
    print(f"Successfully converted: {converted_count} images.")
    print(f"Skipped (already up-to-date): {skipped_count} images.")
    print("Conversion process finished.")


if __name__ == "__main__":
    target_directory = os.path.join(
        "src", "chat", "features", "games", "blackjack-web", "public"
    )

    if not os.path.isdir(target_directory):
        print(f"Error: The target directory '{target_directory}' does not exist.")
        print(
            "Please ensure you are running this script from the project's root directory."
        )
    else:
        convert_images_to_webp(target_directory)
