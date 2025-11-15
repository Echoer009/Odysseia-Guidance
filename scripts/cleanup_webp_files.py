import os


def cleanup_webp_files(root_dir):
    """
    Recursively finds and deletes all .webp files in a directory.

    Args:
        root_dir (str): The root directory to start searching from.
    """
    print(f"Starting cleanup of .webp files in directory: {root_dir}")
    deleted_count = 0

    for subdir, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".webp"):
                file_path = os.path.join(subdir, file)
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")

    print("\n--- Cleanup Summary ---")
    print(f"Successfully deleted: {deleted_count} .webp files.")
    print("Cleanup process finished.")


if __name__ == "__main__":
    # The target directory is the 'public' folder for the blackjack game
    target_directory = os.path.join(
        "src", "chat", "features", "games", "blackjack-web", "public"
    )

    if not os.path.isdir(target_directory):
        print(f"Error: The target directory '{target_directory}' does not exist.")
        print(
            "Please ensure you are running this script from the project's root directory."
        )
    else:
        cleanup_webp_files(target_directory)
