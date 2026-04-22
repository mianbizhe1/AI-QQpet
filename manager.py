import psutil
import os

# 获取内存百分比
mem = psutil.virtual_memory()
print(f"总内存: {mem.total / (1024**3):.2f} GB")
print(f"已用: {mem.used / (1024**3):.2f} GB")
print(f"空闲: {mem.available / (1024**3):.2f} GB")
print(f"内存占用率: {mem.percent}%")

disk = psutil.disk_usage('/')
print(f"磁盘总大小: {disk.total / (1024**3):.2f} GB")
print(f"剩余空间: {disk.free / (1024**3):.2f} GB")
print(f"使用率: {disk.percent}%")


def get_top_large_files(path, top_n=10):
    file_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                # 排除符号链接，获取真实大小
                if not os.path.islink(file_path):
                    file_list.append((file_path, os.path.getsize(file_path)))
            except OSError:
                continue

    # 按大小降序排列
    file_list.sort(key=lambda x: x[1], reverse=True)
    return file_list[:top_n]


# 示例：查看下载文件夹前5个大文件
for f, s in get_top_large_files('~/Downloads', 5):
    print(f"{s / (1024 ** 2):.2f} MB - {f}")