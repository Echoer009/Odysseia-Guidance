import os

current_file_path = os.path.abspath(__file__)

scripts_dir = os.path.dirname(current_file_path)

base_dir = os.path.dirname(scripts_dir)

date_dir = os.path.join(base_dir, "data")

print(f"successfully located date dir {date_dir}")

print(f"starting to scan dir {date_dir}\n")

if os.path.isdir(date_dir):
    all_files = os.listdir(date_dir)
    print(f"found the following items in dir {date_dir}")
    for filename in all_files:
        print(f"- {filename}")
else:
    print(f"error, dir {date_dir} not exit or not is a dir")
