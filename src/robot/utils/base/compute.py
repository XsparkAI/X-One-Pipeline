from scipy.spatial.transform import Rotation
import numpy as np

def apply_local_offset_to_global_pose(T_offset, T_current):
    """
    在当前末端位姿 T_current(全局坐标)上，应用局部坐标下的变换 T_offset。
    结果是偏移后的全局位姿 T_target。
    等价于 T_target = T_current @ T_offset
    """
    return T_current @ T_offset

def euler_to_matrix(euler, degrees=False):
    """
    将欧拉角 (roll, pitch, yaw) 和位置 (x, y, z) 转换为 4x4 齐次变换矩阵。

    Args:
        x, y, z: 位置坐标
        roll, pitch, yaw: 欧拉角（按 'xyz' 顺序）
        degrees: 是否使用角度单位，默认为 False（使用弧度）

    Returns:
        4x4 numpy 数组，表示变换矩阵
    """
    x, y, z, roll, pitch, yaw = euler
    r = Rotation.from_euler('xyz', [roll, pitch, yaw], degrees=degrees)
    rotation_matrix = r.as_matrix()  # 得到 3x3 旋转矩阵

    transform_matrix = np.eye(4)
    transform_matrix[:3, :3] = rotation_matrix
    transform_matrix[:3, 3] = [x, y, z]

    return transform_matrix

def matrix_to_xyz_rpy(matrix):
    # 确保是 numpy 数组
    matrix = np.array(matrix)
    
    # 提取位置
    x, y, z = matrix[0:3, 3]

    # 提取旋转部分（前3x3）
    rot_mat = matrix[0:3, 0:3]
    
    # 转换为 RPY (roll, pitch, yaw) 弧度制
    rpy = Rotation.from_matrix(rot_mat).as_euler('xyz', degrees=False)

    # 可选：返回角度制
    # rpy = np.degrees(rpy)

    return np.array([x, y, z, rpy[0], rpy[1], rpy[2]])

def compute_rotate_matrix(pose):
    """将位姿 [x,y,z,roll,pitch,yaw] 转换为齐次变换矩阵 (XYZ欧拉角顺序)"""
    x, y, z, roll, pitch, yaw = pose

    R = Rotation.from_euler('XYZ', [roll, pitch, yaw]).as_matrix()
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [x, y, z]
    
    return T

def compute_local_delta_pose(base_pose, target_pose):
    """
    计算局部坐标系下的位姿增量 (基于base_pose的坐标系)
    参数:
        base_pose: 基准位姿 [x,y,z,roll,pitch,yaw]
        target_pose: 目标位姿 [x,y,z,roll,pitch,yaw]
    返回:
        增量位姿 [delta_x, delta_y, delta_z, delta_roll, delta_pitch, delta_yaw]
    """
    assert len(base_pose) == 6 and len(target_pose) == 6, "输入位姿必须是6维"
    
    # 计算旋转增量
    base_rotate = Rotation.from_euler('XYZ', base_pose[3:])
    target_rotate = Rotation.from_euler('XYZ', target_pose[3:])
    delta_rotate = base_rotate.inv() * target_rotate
    delta_rpy = delta_rotate.as_euler('XYZ', degrees=False)
    
    # 计算平移增量（转换到局部坐标系）
    delta_global = np.array(target_pose[:3]) - np.array(base_pose[:3])
    delta_xyz = base_rotate.inv().apply(delta_global)
    
    return np.concatenate([delta_xyz, delta_rpy])

def apply_local_delta_pose(base_pose, delta_pose):
    """
    将局部坐标系下的增量位姿应用到 base_pose，恢复出 target_pose（全局位姿）
    参数:
        base_pose: 基准位姿 [x, y, z, roll, pitch, yaw]
        delta_pose: 增量位姿 [delta_x, delta_y, delta_z, delta_roll, delta_pitch, delta_yaw]
    返回:
        target_pose: 目标位姿 [x, y, z, roll, pitch, yaw]
    """
    assert len(base_pose) == 6 and len(delta_pose) == 6, "输入位姿必须是6维"

    # 转换为 numpy 数组
    base_pose = np.asarray(base_pose, dtype=np.float64)
    delta_pose = np.asarray(delta_pose, dtype=np.float64)

    # 构建 base 的旋转
    base_rot = Rotation.from_euler('XYZ', base_pose[3:])
    delta_rot = Rotation.from_euler('XYZ', delta_pose[3:])
    
    # 计算目标旋转（全局）
    target_rot = base_rot * delta_rot
    target_rpy = target_rot.as_euler('XYZ', degrees=False)
    
    # 计算目标位置（全局）
    delta_xyz_world = base_rot.apply(delta_pose[:3])
    target_xyz = base_pose[:3] + delta_xyz_world

    # 拼接结果
    return np.concatenate([target_xyz, target_rpy])