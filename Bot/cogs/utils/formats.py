class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural_ = format_spec.partition('|')
        plural_ = plural_ or f'{singular}s'
        return f'{v} {plural_}' if abs(v) != 1 else f'{v} {singular}'


def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return f'{delim.join(seq[:-1])} {final} {seq[-1]}'