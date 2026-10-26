"""Lazy public names for planar geometry, layout and external assets."""

GEOMETRY_EXPORTS = {}
for _module, _names in {
    "shapes": "AnnularSector Sector Annulus ArcBetweenPoints TangentialArc ArcPolygonFromArcs Elbow ScreenRectangle FullScreenRectangle FullScreenFadeRectangle VDict Polygram RegularPolygram ConvexHull Polyline CubicBezier ArcPolygon VectorizedPoint",
    "coordinates": "SmallDot Vector VectorMobject DoubleArrow CurvedArrow CurvedDoubleArrow TangentLine StrokeArrow",
    "functions": "ParametricCurve FunctionGraph",
    "axes": "NumberLine UnitInterval Axes NumberPlane ComplexPlane PolarPlane ThreeDAxes tick_range c2p p2c coords_to_point point_to_coords number_to_point point_to_number polar_to_point",
    "annotations": "Brace BraceBetweenPoints LineBrace BackgroundRectangle Cross DashedVMobject Angle RightAngle AnnotationDot DimensionLine LabeledDot Label LabeledLine LabeledArrow Title line_intersection angle_value",
    "decor": "Cutout Checkmark Exmark Clock VHighlight TracingTail CurvesAsSubmobjects",
    "tables": "Matrix MatrixMobject Table MobjectTable TexMatrix MathTable IntegerTable DecimalTable matrix_bracket",
    "svg": "SVGMobject clip_layers",
    "image": "ImageMobject pixel_size",
    "compositor_types": "Layer Mask",
    "probability": "SampleSpace",
}.items():
    GEOMETRY_EXPORTS.update({name: "janim.core." + _module for name in _names.split()})
