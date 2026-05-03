# ROS2 Files and Explanations

## Launch file (Python)

### Launch file in `robot_description` project

1. Imports

    ```python
        from launch import LaunchDescription
        from launch_ros.actions import Node
        from launch.substitutions import Command, PathJoinSubstitution
        from launch_ros.substitutions import FindPackageShare
    ```

    - `LaunchDescription` -> container for everything we start
    - `Node` -> represents a ROS node to launch
    - `FindPackageShare` -> finds where your package is
    - `PathJoinSubstitution` -> builds the correct path
    - `Command` -> reads file contents, passes it as a string to ROS

2. Function `generate_launch_description`

    ROS calls this function to get what it should launch

    ```python
        def generate_launch_description():
         return LaunchDescription([])
    ```

    - `LaunchDescription` -> Container (currently empty = no nodes yet)
    1. Node (RViz)

        ```python
            rviz_config = PathJoinSubstitution([
                FindPackageShare('rover_description'),
                'rviz',
                'rover.rviz'
            ])

            rviz_node = Node(
                package='rviz2',
                executable='rviz2',
                arguments=['-d', rviz_config]
            )

            return LaunchDescription([
                rviz_node
            ])
        ```

        - `rviz_node` -> start a ROS node
            - which package -> `package='rviz2'`
            - which program inside that package -> `executable='rviz2'`
            - load display config file -> `-d`

    2. Load URDF file

        ```python
            urdf_path = PathJoinSubstitution([
                FindPackageShare('rover_description'),
                'urdf',
                'rover.urdf'
            ])
        ```

        - `FindPackageShare` -> finds installed package location
        - `urdf` -> folder
        - `rover.urdf` -> file
          Result: `/path/to/install/rover_description/urdf/rover.urdf`

    3. Add Parameter to a Node (rsp_node)

        ```python
            rsp_node = Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                parameters=[{
                    'robot_description': Command(['cat ', urdf_path])
                }]
            )
        ```

        - `parameters` -> list of ROS parameters (see `ros2 param list`)
        - `{} dictionary` -> key-value pairs
            - `robot_description` -> standard parameter name expected by the node
        - `Command([...])` -> runs shell command, captures output and returns it as string
            - `"cat file"` -> reads file contents

3. Run launch file

    `ros2 launch <package_name> <launch_file_name> <launch_arguments>:=<value>`

    For this project:
    `ros2 launch rover_description display.launch.py`

---

### Launch file in `robot_gazebo` project

1. Run Gazebo

    ```python
        from launch.actions import ExecuteProcess

        world_path = PathJoinSubstitution([
            FindPackageShare('rover_gazebo'),
            'worlds',
            'empty.sdf'
        ])

        gazebo = ExecuteProcess(
            cmd=['gz', 'sim', world_path],
            output='screen'
        )
    ```

    - `ExecuteProcess` -> used for running any system commands
        - `cmd` -> first item is executable, rest are arguments to it
        - `output` ->**_(defaults to log)_** defines where the program's logs(stdout/stderr) go. Common options:
            - `screen` -> prints logs directly in terminal
            - `log` -> saves logs to ROS log files(~/.ros/log/)

2. Spawn robot into Gazebo world

    ```python
        spawn_robot = Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-name', 'rover_bot',
                '-topic', 'robot_description'
            ],
            output='screen'
        )
    ```

    - `ros_gz_sim` -> ROS-Gazebo integration package
    - `create` -> the tool that spawns entities into Gazebo
    - `arguments` -> command line inputs
        - `-name` -> name of robot inside Gazebo
        - `-topic` -> where robot model is

    The code above equals to `ros2 run ros_gz_sim create -name rover_bot -topic robot_description`

---

## Setup file

If a file is not declared in `setup.py`:

- ROS will NOT copy it into the install space(~/rover_ws/install/rover_description/)
- ROS will NOT find it
- `ros2 launch` will fail

> [!IMPORTANT]
> Modify `setup.py` whenever you add:
>
> - URDF files
> - config files
> - launch files
> - YAML files
> - meshes

1. Open `setup.py`

    `nano ~/rover_ws/src/rover_description/setup.py`

2. Understanding `data_files=[...]`

    Controls which non-Python files get installed

    Default entries:

    ```python
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name])
    ```

    -> Registers the package in ROS

    ```python
        ('share/' + package_name, ['package.xml'])
    ```

    -> Installs `package.xml`

3. Adding entries to `setup.py`
    1. Install URDF file

        Add this to `data_files`:

        `('share/rover_description/urdf', ['urdf/rover.urdf']),`
        - `share/rover_description/urdf` -> destination
        - `urdf/rover.urdf` -> source file

    2. Install launch file

        Add this to `data_files`:

        `('share/rover_description/launch', ['launch/display.launch.py']),`

        ROS looks in `install/rover_description/share/rover_description/launch/` when you run `ros2 launch ...`

        If file is not there, launch fails

---

## URDF file

1. Links

    ```xml
        <?xml version="1.0"?>
        <robot name="rover_bot">

            <!-- Base Link and Chassis-->
            <link name="base_link"/>

            <link name="chassis">
                <visual>
                    <origin xyz="0 0 0.07" />
                    <geometry>
                        <box size="0.5 0.3 0.1" />
                    </geometry>
                    <material name="grey" />
                </visual>
                <collision>
                    <origin xyz="0 0 0.07" />
                    <geometry>
                        <box size="0.5 0.3 0.1" />
                    </geometry>
                </collision>
            </link>
        </robot>
    ```

    - `visual` -> specifies the shape of the object
        - `geometry` -> shape of the visual object. This can be one of the following `box`, `cylinder`, `sphere`, `mesh`
        - `origin` -> _*_(defaults to identity)_**
            - `xyz` -> **_(defaults to zero vector)_**
            - `rpy` -> **_(defaults to identity)_**
        - `material` -> **_(you can reference the material by `name` attribute if you specify a material element outside of the `link` object, in the top level of `robot` element)_**
            - `color` -> `rgba` in the range of [0,1]
            - `texture` -> texture specified by a `filename`
    - `collision` -> used for physics collision calculations. We can set `geometry` and `origin`: same options as in `visual`
    - `inertial` -> determines how the link responds to forces
        - `mass` -> mass of the link
        - `origin` ->**_(optional)_** centre of mass, the point the link could "balance" on
            - `xyz` -> **_(defaults to zero vector)_** represents the position vector from link-frame-origin to center of mass
            - `rpy` -> **_(defaults to identity)_** represents the orientation of unit vectors of the center of mass relative to link-frame as a sequence of Euler rotations in radians
        - `inertia` -> rotational inertia matrix. Links's moments of inertia(ixx,iyy,izz) and product of inertia(ixy,ixz,iyz) about the center of mass for the fixed unit vectors of the center of mass

2. Joints

    ```xml
        <joint name="left_wheel_joint" type="continuous">
            <parent link="chassis" />
            <child link="left_wheel" />
            <origin xyz="0.2 0.16 0.07" rpy="-1.57 0 0" />
            <axis xyz="0 0 1" />
        </joint>
    ```

    - `joint type` -> can be one of the following:
        - `revolute` -> hinge joint that rotates along the axis and has a limited range specified by `upper` and `lower` limits
        - `continuous` -> hinge joint that rotates around the axis and has no limits
        - `prismatic` -> sliding joint that slides along the axis and has a limited range specified by `upper` and `lower` limits
        - `fixed` -> no movement = does not require `<axis>, <calibration>, <dynamics>, <limits> or <safety_controller>`
        - `floating` -> allows motion for all 6 DoF
        - `planar` -> allows motion in a plane perpendicular to the axis

    - `origin` -> **_(optional: defaults to identity)_** transform from parent link to child link located at the origin of the child link
        - `xyz` -> offsets in metres
        - `rpy` -> rotation around axes in radians
    - `axis` -> **_(optional: defaults to (1,0,0))_** axis of rotation or axis of translation for joints **_(fixed and floating do not use the axis field)_**
    - `limit` -> **_(required only for revolute and prismatic)_**
        - `lower` -> **_(optional: defaults to 0)_** in radians for revolute, in metres for prismatic
        - `upper` -> **_(optional: defaults to 0)_** in radians for revolute, in metres for prismatic
        - `effort` -> **_(required)_*_ enforcing the maximum joint effort (|applied effort| < |effort|)
        - `velocity` -> ***(required)***enforcing the maximum joint velocity (in radians per second [rad/s] for revolute joints, in metres per second [m/s] for prismatic joints)

3. Extra Tags
    - `gazebo` -> specify certain parameters that are used in gazebo simulation
    - `transmission` -> provides more detail about how the joints are driven by **physical actuators**

---

## Useful Commands

### List all packages

```bash
    ros2 pkg list
```

### Find a package

```bash
    ros2 pkg list | grep robot
```

### See what a package contains

```bash
    ros2 pkg executables robot_state_publisher
```

Outputs `robot_state_publisher robot_state_publisher`. This means:

- package: `robot_state_publisher`
- executable (Node): `robot_state_publisher`
