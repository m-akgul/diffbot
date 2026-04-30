# ROS2 Files and Explanations

## Launch file (Python)

1. Imports

   ```python
       from launch import LaunchDescription
       from launch_ros.actions import Node
       from launch.substitutions import Command
       from launch.substitutions import PathJoinSubstitution
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
          rviz_node = Node(
            package='rviz2',
            executable='rviz2'
          )

          return LaunchDescription([
              rviz_node
          ])
      ```

      - `rviz_node` -> start a ROS node
        - which package -> `package='rviz2'`
        - which program inside that package -> `executable='rviz2'`

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

      - `parameters` -> list of parameters
      - `{} dictionary` -> key-value pairs
        - `robot_description` -> standard parameter name expected by the node
      - `Command([...])` -> runs shell command
      - `"cat file"` -> reads file contents

3. Run launch file

   `ros2 launch <package_name> <launch_file_name> <launch_arguments>:=<value>`

   For this project:
   `ros2 launch rover_description display.launch.py`

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

   URDF file and launch file are NOT installed
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
