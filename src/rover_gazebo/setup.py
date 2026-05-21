from glob import glob

from setuptools import find_packages, setup

package_name = 'rover_gazebo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # ament index marker - required so ros2 can find the package
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # package.xml
        ('share/' + package_name, ['package.xml']),
        # Gazebo world file
        ('share/' + package_name + '/worlds', glob('worlds/*')),
        # Launch files
        ('share/' + package_name + '/launch', glob('launch/*')),
        # Config files
        ('share/' + package_name + '/config', glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='merta',
    maintainer_email='81179831+m-akgul@users.noreply.github.com',
    description='Robot simulation package for rover_bot',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
        ],
    },
)
