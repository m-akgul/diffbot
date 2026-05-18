from glob import glob

from setuptools import find_packages, setup

package_name = 'rover_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='merta',
    maintainer_email='81179831+m-akgul@users.noreply.github.com',
    description='Control interfaces for rover robot',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'teleop_gui = rover_control.teleop_gui:main',
            'mux_node = rover_control.mux_node:main',
            'teleop_arbiter = rover_control.teleop_arbiter:main',
        ],
    },
)
