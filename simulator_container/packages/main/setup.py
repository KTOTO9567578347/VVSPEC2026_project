from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'main'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, "launch"), glob('launch/*')),
        (os.path.join('share', package_name, "params"), glob('params/*')),
        (os.path.join('share', package_name, "maps"), glob('maps/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='andbondstyle@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
)
