"""
Utility untuk smoothing nilai numerik (1D atau berupa tuple/list koordinat)
menggunakan Exponential Moving Average (EMA).

EMA dipilih karena ringan secara komputasi (penting untuk real-time) dan
cukup efektif mengurangi jitter tanpa menambah latency signifikan.
"""


class EMASmoother:
    """
    Exponential Moving Average smoother.

    smoothed = alpha * new_value + (1 - alpha) * smoothed_prev

    alpha mendekati 1 -> responsif tapi kurang smooth (lag rendah)
    alpha mendekati 0 -> sangat smooth tapi lag tinggi

    Mendukung input berupa angka tunggal (float/int) atau tuple/list
    koordinat (misal (x, y)).
    """

    def __init__(self, alpha: float = 0.5):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha harus berada di rentang (0, 1]")
        self.alpha = alpha
        self._value = None

    def update(self, new_value):
        if self._value is None:
            self._value = new_value
            return self._value

        if isinstance(new_value, (tuple, list)):
            self._value = type(new_value)(
                self.alpha * nv + (1 - self.alpha) * ov
                for nv, ov in zip(new_value, self._value)
            )
        else:
            self._value = self.alpha * new_value + (1 - self.alpha) * self._value

        return self._value

    @property
    def value(self):
        return self._value

    def reset(self):
        self._value = None