"""Lazy public names for scenes and animations."""


ANIMATION_EXPORTS = {}
for module, names in (
    ("animation.animation", "Animation Wait prepare_animation turn_animation_into_updater"),
    ("animation.transform", "Transform ReplacementTransform TransformFromCopy MoveToTarget Restore"),
    ("animation.composition", "AnimationGroup LaggedStart LaggedStartMap Succession"),
    ("animation.creation", "ShowCreation Create Uncreate SpiralIn DrawBorderThenFill Write Unwrite GrowFromPoint GrowFromCenter GrowFromEdge GrowArrow SpinInFromNothing ShrinkToCenter UpdateFromAlphaFunc UpdateFromFunc"),
    ("animation.fading", "FadeIn FadeOut FadeInFromPoint FadeOutToPoint VFadeIn VFadeOut VFadeInThenOut FadeTransform FadeTransformPieces"),
    ("animation.camera", "CameraFrame"),
    ("animation.homotopy", "Homotopy SmoothedVectorizedHomotopy ComplexHomotopy ApplyWave PhaseFlow ApplyPointwiseFunction ApplyPointwiseFunctionToCenter ApplyMatrix ApplyComplexFunction ApplyFunction ApplyMethod"),
    ("animation.rotation", "Rotating Rotate MoveAlongPath ClockPassesTime"),
    ("animation.indication", "Indicate FocusOn Flash Circumscribe Wiggle FlashyFadeIn ShowPassingFlashWithThinningStrokeWidth AnimationOnSurroundingRectangle ShowPassingFlashAround ShowCreationThenDestructionAround ShowCreationThenFadeAround"),
    ("animation.numbers", "ChangingDecimal ChangeDecimalToValue CountInFrom"),
    ("animation.passing", "VShowPassingFlash ShowPassingFlash FlashAround FlashUnder ShowCreationThenDestruction ShowCreationThenFadeOut TurnInsideOut"),
    ("animation.sugar", "FadeToColor ScaleInPlace CyclicReplace Swap CircleIndicate Broadcast BroadcastRipple Blink ShowIncreasingSubsets ShowSubmobjectsOneByOne MaintainPositionRelativeTo AddTextLetterByLetter TypeWithCursor AddTextWordByWord RemoveTextLetterByLetter UntypeWithCursor"),
    ("core.annotations", "SurroundingRectangle Underline"),
    ("core.trackers", "ValueTracker ComplexValueTracker always_redraw TracedPath"),
    ("scene.scene", "Scene MovingCameraScene ThreeDScene render render_frame render_frame_motion animation_map describe render_segment render_from render_parallel count_frames"),
    ("scene.checkpoints", "checkpoint_states checkpoint_valid clear_checkpoints"),
):
    ANIMATION_EXPORTS.update({name: "janim." + module for name in names.split()})
