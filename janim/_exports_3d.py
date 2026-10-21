"""Lazy public 3D, cloud, field, model and simulation entry points."""

THREE_D_EXPORTS = {
    name: "janim.core.surface"
    for name in (
        "Surface", "ParametricSurface", "Sphere", "Torus", "PlaneXY", "Cylinder", "Cone",
        "Dot3D", "Line3D", "Arrow3D", "SurfaceMesh", "VGroup3D", "Polyhedron",
        "Tetrahedron", "Octahedron", "Icosahedron", "Dodecahedron", "Square3D",
        "Cube", "VCube", "Prism", "VPrism", "Prismify", "triangle_indices",
    )
}
THREE_D_EXPORTS.update(
    {name: "janim.core.dots" for name in ("DotCloud", "TrueDot", "GlowDots", "GlowDot", "PGroup")},
)
THREE_D_EXPORTS.update(
    {
        "TexturedSurface": "janim.core.image",
        "ImplicitFunction": "janim.core.implicit",
        "ThreeDModel": "janim.core.model",
    },
)
THREE_D_EXPORTS.update(
    {
        name: "janim.core.fields"
        for name in (
            "VectorField", "TimeVaryingVectorField", "StreamLines", "AnimatedStreamLines",
            "ode_solution_points",
        )
    },
)
THREE_D_EXPORTS.update(
    {name: "janim.ode" for name in ("ODEProblem", "Tsit5", "init", "solve", "step")},
)
