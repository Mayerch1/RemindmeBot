from unittest import main
import test.BasicParseTest as BPT
import test.WrapParseTest as WPT
import test.AmbigParseTest as APT
import test.TimezoneParseTest as TPT
import test.AbsParseTest as AbPT
import test.CombineParseTest as CPT
import test.IntervalTest as ITT


if __name__ == '__main__':
    main(module=AbPT, exit=False)

    main(module=BPT, exit=False)
    main(module=WPT, exit=False)
    main(module=APT, exit=False)
    main(module=TPT, exit=False)
    main(module=CPT, exit=False)
    main(module=ITT, exit=False)
    