from setuptools import find_packages, setup

package_name = 'rover_description'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/rover_description/urdf', ['urdf/rover.urdf']),
        ('share/rover_description/launch', ['launch/display.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='merta',
    maintainer_email='81179831+m-akgul@users.noreply.github.com',
    description='Robot description package for rover_bot',
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
