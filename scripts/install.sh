# compile project
pip install -e .

# install y1_sdk
cd third_party/
git clone https://github.com/IMETA-Robotics/y1_sdk_python.git
cd y1_sdk_python/y1_sdk
pip install -e .
cd ../..