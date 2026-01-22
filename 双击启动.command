#!/bin/bash
# 自动定位到脚本所在文件夹
cd "$(dirname "$0")"

# 运行本地版代码
# 注意：这里调用的是我们之前写好的 app_local.py
python3 -m streamlit run app_local.py --global.developmentMode=false

# 如果程序意外退出，保留窗口查看报错信息
read -p "程序已关闭，按回车键退出..."