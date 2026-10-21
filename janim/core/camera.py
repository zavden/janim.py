"""Camera geometry and projection inputs."""

import math

import numpy as np

from janim.constants import DEG, FRAME_HEIGHT, FRAME_WIDTH
from janim.png import dimensions
from .algebra import (
    Quat,
    apply_matrix_rows,
    euler_zxz_from_quat,
    quat_axis_angle,
    quat_from_euler_zxz,
    quat_identity,
    quat_mul,
    quat_to_matrix,
)
from ._atan import scalar_atan
from ._julia_math import tan
from .colorspace import _as_rgba


class Camera:
    def __init__(
        self,
        *,
        width=960,
        height=540,
        frame_width=FRAME_WIDTH,
        frame_height=FRAME_HEIGHT,
        fovy=45 * DEG,
        background=(0, 0, 0, 1),
        light_position=(-10, 10, 10),
        orientation=(0, 0, 0, 1),
        center_point=(0, 0, 0),
    ):
        self.width, self.height = dimensions(width, height)
        self.frame_width = float(frame_width)
        self.frame_height = float(frame_height)
        self.fovy = float(fovy)
        self.background = background
        self.light_position = np.array(light_position, dtype=np.float32)
        self.orientation = Quat(orientation)
        self.center_point = np.array(center_point, dtype=np.float32)

    @property
    def background(self):
        return self._background

    @background.setter
    def background(self, color):
        # A camera background already carries alpha; the style helper's
        # default opacity=1 would silently turn a transparent clear opaque.
        self._background = _as_rgba(color)

    def get_scale(self):
        return self.frame_height / FRAME_HEIGHT

    def get_focal_distance(self):
        # Janim's own tan and atan: glibc's differ in the last bit on 4% of the angles
        return 0.5 * self.frame_height / tan(0.5 * self.fovy)

    def set_focal_distance(self, distance):
        self.fovy = 2 * scalar_atan(0.5 * self.frame_height / float(distance))
        return self

    def get_euler_angles(self):
        return euler_zxz_from_quat(self.orientation)

    def set_euler_angles(self, *, theta=None, phi=None, gamma=None):
        angles = list(self.get_euler_angles())
        for index, value in enumerate((theta, phi, gamma)):
            if value is not None:
                angles[index] = float(value)
        self.orientation = quat_identity() if not any(angles) else quat_from_euler_zxz(*angles)
        return self

    def reorient(
        self,
        theta=None,
        phi=None,
        gamma=None,
        *,
        center=None,
        height=None,
    ):
        self.set_euler_angles(
            theta=None if theta is None else theta * DEG,
            phi=None if phi is None else phi * DEG,
            gamma=None if gamma is None else gamma * DEG,
        )
        if center is not None:
            self.center_point = np.array(center, dtype=np.float32)
        if height is not None:
            self.frame_width *= height / self.frame_height
            self.frame_height = float(height)
        return self

    def rotate(self, angle, axis=(0, 0, 1)):
        self.orientation = quat_mul(quat_axis_angle(axis, angle), self.orientation)
        return self

    def get_theta(self):
        return self.get_euler_angles()[0]

    def get_phi(self):
        return self.get_euler_angles()[1]

    def get_gamma(self):
        return self.get_euler_angles()[2]

    def increment_euler_angles(self, *, dtheta=0.0, dphi=0.0, dgamma=0.0):
        """GL's increment_euler_angles: adds and clamps phi to [0, pi] (zxz)."""
        theta, phi, gamma = self.get_euler_angles()
        self.orientation = quat_from_euler_zxz(
            theta + float(dtheta),
            min(max(phi + float(dphi), 0.0), math.pi),
            gamma + float(dgamma),
        )
        return self

    def increment_theta(self, value, *, units=1.0):
        return self.increment_euler_angles(dtheta=float(value) * float(units))

    def increment_phi(self, value, *, units=1.0):
        return self.increment_euler_angles(dphi=float(value) * float(units))

    def increment_gamma(self, value, *, units=1.0):
        return self.increment_euler_angles(dgamma=float(value) * float(units))

    def scale_frame(self, factor, *, about=None):
        """Zoom about `about` (the centre by default), in f64."""
        center = self.center_point.astype(np.float64)
        pivot = center if about is None else np.asarray(about, dtype=np.float32).astype(np.float64)
        factor = float(factor)
        self.center_point = (pivot + factor * (center - pivot)).astype(np.float32)
        self.frame_height *= factor
        self.frame_width *= factor
        return self

    def reset_camera(self):
        """CameraFrame's to_default_state: identity, origin, the default frame."""
        self.orientation = quat_identity()
        self.center_point = np.zeros(3, dtype=np.float32)
        self.frame_width = FRAME_WIDTH
        self.frame_height = FRAME_HEIGHT
        return self

    def get_view_matrix(self):
        rotation = quat_to_matrix(self.orientation)
        result = np.zeros((4, 4), dtype=np.float64)
        result[3, 3] = 1
        result[:3, :3] = rotation.T
        center = -self.center_point.astype(np.float64)
        # The compensated array helper loses the sign of an exact zero;
        # these three scalar products preserve StaticArrays' nested fma.
        for i in range(3):
            result[i, 3] = math.fma(
                float(rotation[2, i]),
                float(center[2]),
                math.fma(float(rotation[1, i]), float(center[1]), float(rotation[0, i] * center[0])),
            )
        scale = self.get_scale()
        if scale > 0:
            result[:3] /= scale
        return result

    def get_implied_camera_location(self):
        rotation = quat_to_matrix(self.orientation)
        return self.center_point.astype(np.float64) + self.get_focal_distance() * rotation[:, 2]


def camera_uniforms(camera, *, flip_y=False):
    scale = camera.get_scale()
    return {
        "view": camera.get_view_matrix().astype(np.float32),
        "frame_scale": np.float32(scale),
        "frame_rescale_factors": np.array(
            (2 / FRAME_WIDTH, (-1 if flip_y else 1) * 2 / FRAME_HEIGHT, scale / camera.get_focal_distance()),
            dtype=np.float32,
        ),
        "pixel_size": np.float32(camera.frame_width / camera.width),
        "camera_position": camera.get_implied_camera_location().astype(np.float32),
        "light_position": camera.light_position,
    }


def get_view_matrix(camera):
    return camera.get_view_matrix()


def focal_distance(camera):
    return camera.get_focal_distance()
