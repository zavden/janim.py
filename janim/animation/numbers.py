"""ManimGL's decimal animations (animation/numbers.py:14-63): a number changing along an alpha."""

from janim.core.bezier import interpolate

from .animation import Animation


class ChangingDecimal(Animation):
    def __init__(self, decimal_mob, number_update_func, *, suspend_mobject_updating=False, **kwargs):
        if not callable(getattr(decimal_mob, "set_value", None)):
            raise TypeError("ChangingDecimal animates a DecimalNumber")
        self.number_update_func = number_update_func
        super().__init__(decimal_mob, suspend_mobject_updating=suspend_mobject_updating, **kwargs)

    def interpolate_mobject(self, alpha):
        self.mobject.set_value(self.number_update_func(self.time_spanned_alpha(alpha)))


class ChangeDecimalToValue(ChangingDecimal):
    def __init__(self, decimal_mob, target_number, **kwargs):
        start_number = decimal_mob.get_value()
        super().__init__(decimal_mob, lambda a: interpolate(start_number, target_number, a), **kwargs)


class CountInFrom(ChangingDecimal):
    def __init__(self, decimal_mob, source_number=0, **kwargs):
        start_number = decimal_mob.get_value()
        super().__init__(decimal_mob, lambda a: interpolate(source_number, start_number, a), **kwargs)
