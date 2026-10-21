"""An animatable view of Camera, with detached snapshots and quaternion slerp."""

import math

import numpy as np

from janim.constants import FRAME_HEIGHT, FRAME_WIDTH
from janim.core.algebra import quat_from_euler_zxz, quat_identity, quat_slerp
from janim.core.camera import Camera
from janim.core.mobject import Mobject


def copy_camera(camera):
    return Camera(
        width=camera.width,
        height=camera.height,
        frame_width=camera.frame_width,
        frame_height=camera.frame_height,
        fovy=camera.fovy,
        background=camera.background.copy(),
        light_position=camera.light_position.copy(),
        orientation=camera.orientation.copy(),
        center_point=camera.center_point.copy(),
    )


class CameraFrame(Mobject):
    is_interpolable = True

    def __init__(self, camera=None):
        super().__init__()
        self.camera = Camera() if camera is None else camera
        self.camera.frame = self

    def copy(self, deep=False):
        result = super().copy(deep=deep)
        result.camera = copy_camera(self.camera)
        result.camera.frame = result
        return result

    def align_data(self, other, **kwargs):
        return self

    def interpolate(self, first, second, alpha, **kwargs):
        a, b, camera = first.camera, second.camera, self.camera
        alpha = float(alpha)
        camera.center_point = (a.center_point.astype(np.float64) + alpha * (b.center_point.astype(np.float64) - a.center_point.astype(np.float64))).astype(np.float32)
        for name in ("frame_width", "frame_height", "fovy"):
            start, end = getattr(a, name), getattr(b, name)
            setattr(camera, name, start + alpha * (end - start))
        camera.orientation = quat_slerp(a.orientation, b.orientation, alpha)
        return self.note_changed_data()

    def become(self, other, **kwargs):
        for name in ("center_point", "orientation"):
            setattr(self.camera, name, getattr(other.camera, name).copy())
        for name in ("frame_width", "frame_height", "fovy"):
            setattr(self.camera, name, getattr(other.camera, name))
        return self.note_changed_data()

    def get_center(self):
        return self.camera.center_point.copy()

    def get_width(self):
        return self.camera.frame_width

    def get_height(self):
        return self.camera.frame_height

    def get_bounding_box_point(self, direction):
        direction = np.asarray(direction, dtype=np.float32)
        half = np.array((self.get_width() / 2, self.get_height() / 2, 0), dtype=np.float64)
        return (self.camera.center_point.astype(np.float64) + np.sign(direction.astype(np.float64)) * half).astype(np.float32)

    def get_bounding_box(self):
        return np.array([self.get_bounding_box_point((-1, -1, 0)), self.get_center(), self.get_bounding_box_point((1, 1, 0))])

    def move_to(self, point, **kwargs):
        point = point.get_center() if isinstance(point, Mobject) else point
        self.camera.center_point = np.array(point, dtype=np.float32)
        return self.note_changed_data()

    def shift(self, direction):
        self.camera.center_point = (self.camera.center_point.astype(np.float64) + np.asarray(direction, dtype=np.float32).astype(np.float64)).astype(np.float32)
        return self.note_changed_data()

    def scale(self, factor, about_point=None, about_edge=(0, 0, 0)):
        if about_point is None and any(about_edge):
            about_point = self.get_bounding_box_point(about_edge)
        center = self.camera.center_point.astype(np.float64)
        pivot = center if about_point is None else np.asarray(about_point, dtype=np.float32).astype(np.float64)
        factor = float(factor)
        self.camera.center_point = (pivot + factor * (center - pivot)).astype(np.float32)
        self.camera.frame_height *= factor
        self.camera.frame_width *= factor
        return self.note_changed_data()

    def scale_frame(self, factor, *, about=None):
        return self.scale(factor, about_point=about)

    def set_frame_height(self, height):
        self.camera.frame_width *= height / self.camera.frame_height
        self.camera.frame_height = float(height)
        return self.note_changed_data()

    def set_frame_width(self, width):
        return self.set_frame_height(width * self.camera.frame_height / self.camera.frame_width)

    def set_height(self, height, **kwargs):
        return self.set_frame_height(height)

    def set_width(self, width, **kwargs):
        return self.set_frame_width(width)

    def reorient(self, *args, **kwargs):
        # ManimGL spells the angles theta_degrees/phi_degrees/gamma_degrees
        for name in ("theta", "phi", "gamma"):
            if name + "_degrees" in kwargs:
                kwargs[name] = kwargs.pop(name + "_degrees")
        self.camera.reorient(*args, **kwargs)
        return self.note_changed_data()

    def rotate(self, angle, axis=(0, 0, 1)):
        self.camera.rotate(angle, axis)
        return self

    def get_euler_angles(self):
        return self.camera.get_euler_angles()

    def get_theta(self):
        return self.get_euler_angles()[0]

    def get_phi(self):
        return self.get_euler_angles()[1]

    def get_gamma(self):
        return self.get_euler_angles()[2]

    def set_euler_angles(self, **kwargs):
        self.camera.set_euler_angles(**kwargs)
        return self

    def increment_euler_angles(self, *, dtheta=0.0, dphi=0.0, dgamma=0.0):
        theta, phi, gamma = self.get_euler_angles()
        self.camera.orientation = quat_from_euler_zxz(theta + dtheta, min(max(phi + dphi, 0), math.pi), gamma + dgamma)
        return self

    def increment_theta(self, value, *, units=1.0):
        return self.increment_euler_angles(dtheta=float(value) * float(units))

    def increment_phi(self, value, *, units=1.0):
        return self.increment_euler_angles(dphi=float(value) * float(units))

    def increment_gamma(self, value, *, units=1.0):
        return self.increment_euler_angles(dgamma=float(value) * float(units))

    def reset_frame(self):
        self.camera.orientation = quat_identity()
        self.camera.center_point = np.zeros(3, dtype=np.float32)
        self.camera.frame_width = FRAME_WIDTH
        self.camera.frame_height = FRAME_HEIGHT
        return self.note_changed_data()

    to_default_state = reset_frame

    def get_focal_distance(self):
        return self.camera.get_focal_distance()

    def set_focal_distance(self, distance):
        self.camera.set_focal_distance(distance)
        return self
