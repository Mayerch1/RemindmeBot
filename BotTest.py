from unittest import main
import unit_tests.BasicParseTest as BPT
import unit_tests.WrapParseTest as WPT
import unit_tests.AmbigParseTest as APT
import unit_tests.TimezoneParseTest as TPT
import unit_tests.AbsParseTest as AbPT
import unit_tests.CombineParseTest as CPT
import unit_tests.IntervalTest as ITT


if __name__ == '__main__':
    main(module=AbPT, exit=False)

    main(module=BPT, exit=False)
    main(module=WPT, exit=False)
    main(module=APT, exit=False)
    main(module=TPT, exit=False)
    main(module=CPT, exit=False)
    main(module=ITT, exit=False)
    