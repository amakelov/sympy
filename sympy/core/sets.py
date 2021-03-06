from sympy.core.sympify import _sympify, sympify, SympifyError
from sympy.core.basic import Basic
from sympy.core.singleton import Singleton, S
from sympy.core.evalf import EvalfMixin
from sympy.core.numbers import Float
from sympy.core.containers import Tuple

from sympy.mpmath import mpi, mpf
from sympy.assumptions import ask
from sympy.logic.boolalg import And, Or

class Set(Basic):
    """
    The base class for any kind of set.

    This is not meant to be used directly as a container of items.
    It does not behave like the builtin set; see FiniteSet for that.

    Real intervals are represented by the Interval class and unions of sets
    by the Union class. The empty set is represented by the EmptySet class
    and available as a singleton as S.EmptySet.
    """
    is_number = False
    is_iterable = False
    is_interval = False

    is_FiniteSet = False
    is_Interval = False
    is_ProductSet = False
    is_Union = False
    is_Intersection = None
    is_EmptySet = None
    is_UniversalSet = None

    def union(self, other):
        """
        Returns the union of 'self' and 'other'.

        As a shortcut it is possible to use the '+' operator:

        >>> from sympy import Interval, FiniteSet
        >>> Interval(0, 1).union(Interval(2, 3))
        [0, 1] U [2, 3]
        >>> Interval(0, 1) + Interval(2, 3)
        [0, 1] U [2, 3]
        >>> Interval(1, 2, True, True) + FiniteSet(2, 3)
        (1, 2] U {3}

        Similarly it is possible to use the '-' operator for set differences:

        >>> Interval(0, 2) - Interval(0, 1)
        (1, 2]
        >>> Interval(1, 3) - FiniteSet(2)
        [1, 2) U (2, 3]

        """
        return Union(self, other)

    def intersect(self, other):
        """
        Returns the intersection of 'self' and 'other'.

        >>> from sympy import Interval

        >>> Interval(1, 3).intersect(Interval(1, 2))
        [1, 2]

        """
        return Intersection(self, other)

    def _intersect(self, other):
        """
        This function should only be used internally

        self._intersect(other) returns a new, intersected set if self knows how
        to intersect itself with other, otherwise it returns None

        When making a new set class you can be assured that other will not
        be a Union, FiniteSet, or EmptySet

        Used within the Intersection class
        """
        return None

    @property
    def complement(self):
        """
        The complement of 'self'.

        As a shortcut it is possible to use the '~' or '-' operators:

        >>> from sympy import Interval

        >>> Interval(0, 1).complement
        (-oo, 0) U (1, oo)
        >>> ~Interval(0, 1)
        (-oo, 0) U (1, oo)
        >>> -Interval(0, 1)
        (-oo, 0) U (1, oo)

        """
        return self._complement

    @property
    def _complement(self):
        raise NotImplementedError("(%s)._complement" % self)

    @property
    def inf(self):
        """
        The infimum of 'self'

        >>> from sympy import Interval, Union

        >>> Interval(0, 1).inf
        0
        >>> Union(Interval(0, 1), Interval(2, 3)).inf
        0

        """
        return self._inf

    @property
    def _inf(self):
        raise NotImplementedError("(%s)._inf" % self)

    @property
    def sup(self):
        """
        The supremum of 'self'

        >>> from sympy import Interval, Union

        >>> Interval(0, 1).sup
        1
        >>> Union(Interval(0, 1), Interval(2, 3)).sup
        3

        """
        return self._sup

    @property
    def _sup(self):
        raise NotImplementedError("(%s)._sup" % self)

    def contains(self, other):
        """
        Returns True if 'other' is contained in 'self' as an element.

        As a shortcut it is possible to use the 'in' operator:

        >>> from sympy import Interval

        >>> Interval(0, 1).contains(0.5)
        True
        >>> 0.5 in Interval(0, 1)
        True

        """
        return self._contains(sympify(other, strict=True))

    def _contains(self, other):
        raise NotImplementedError("(%s)._contains(%s)" % (self, other))

    def subset(self, other):
        """
        Returns True if 'other' is a subset of 'self'.

        >>> from sympy import Interval

        >>> Interval(0, 1).contains(0)
        True
        >>> Interval(0, 1, left_open=True).contains(0)
        False

        """
        if isinstance(other, Set):
            return self.intersect(other) == other
        else:
            raise ValueError("Unknown argument '%s'" % other)

    @property
    def measure(self):
        """
        The (Lebesgue) measure of 'self'

        >>> from sympy import Interval, Union

        >>> Interval(0, 1).measure
        1
        >>> Union(Interval(0, 1), Interval(2, 3)).measure
        2

        """
        return self._measure

    @property
    def _measure(self):
        raise NotImplementedError("(%s)._measure" % self)

    def __add__(self, other):
        return self.union(other)

    def __or__(self, other):
        return self.union(other)

    def __and__(self, other):
        return self.intersect(other)

    def __mul__(self, other):
        return ProductSet(self, other)

    def __pow__(self, exp):
        if not sympify(exp).is_Integer and exp>=0:
            raise ValueError("%s: Exponent must be a positive Integer"%exp)
        return ProductSet([self]*exp)

    def __sub__(self, other):
        return self.intersect(other.complement)

    def __neg__(self):
        return self.complement

    def __invert__(self):
        return self.complement

    def __contains__(self, other):
        symb = self.contains(other)
        result = ask(symb)
        if result is None:
            raise TypeError('contains did not evaluate to a bool: %r' % symb)
        return result

    @property
    def is_real(self):
        return False

class ProductSet(Set):
    """
    Represents a Cartesian Product of Sets.

    Returns a cartesian product given several sets as either an iterable
    or individual arguments.

    Can use '*' operator on any sets for convenient shorthand.

    Examples
    ========

        >>> from sympy import Interval, FiniteSet, ProductSet

        >>> I = Interval(0, 5); S = FiniteSet(1, 2, 3)
        >>> ProductSet(I, S)
        [0, 5] x {1, 2, 3}

        >>> (2, 2) in ProductSet(I, S)
        True

        >>> Interval(0, 1) * Interval(0, 1) # The unit square
        [0, 1] x [0, 1]

        >>> coin = FiniteSet('H','T')
        >>> for pair in coin**2: print pair
        (H, H)
        (H, T)
        (T, H)
        (T, T)


    Notes
    =====
    - Passes most operations down to the argument sets
    - Flattens Products of ProductSets

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Cartesian_product
    """
    is_ProductSet = True

    def __new__(cls, *sets, **assumptions):
        def flatten(arg):
            if isinstance(arg, Set):
                if arg.is_ProductSet:
                    return sum(map(flatten, arg.args), [])
                else:
                    return [arg]
            elif is_flattenable(arg):
                return sum(map(flatten, arg), [])
            raise TypeError("Input must be Sets or iterables of Sets")
        sets = flatten(list(sets))

        if EmptySet() in sets or len(sets)==0:
            return EmptySet()

        return Basic.__new__(cls, *sets, **assumptions)

    def _contains(self, element):
        """
        'in' operator for ProductSets

        >>> from sympy import Interval

        >>> (2, 3) in Interval(0, 5) * Interval(0, 5)
        True

        >>> (10, 10) in Interval(0, 5) * Interval(0, 5)
        False

        Passes operation on to constitent sets
        """
        try:
            if len(element) != len(self.args):
                return False
        except TypeError: # maybe element isn't an iterable
            return False
        return And(*[set.contains(item) for set, item in zip(self.sets, element)])

    def _intersect(self, other):
        if not other.is_ProductSet:
            return None
        if len(other.args) != len(self.args):
            return S.EmptySet
        return ProductSet(a.intersect(b)
                for a, b in zip(self.sets, other.sets))

    @property
    def sets(self):
        return self.args

    @property
    def _complement(self):
        # For each set consider it or it's complement
        # We need at least one of the sets to be complemented
        # Consider all 2^n combinations.
        # We can conveniently represent these options easily using a ProductSet
        switch_sets = ProductSet(FiniteSet(s, s.complement) for s in self.sets)
        product_sets = (ProductSet(*set) for set in switch_sets)
        # Union of all combinations but this one
        return Union(p for p in product_sets if p != self)

    @property
    def is_real(self):
        return all(set.is_real for set in self.sets)

    @property
    def is_iterable(self):
        return all(set.is_iterable for set in self.sets)

    def __iter__(self):
        if self.is_iterable:
            from sympy.core.compatibility import product
            return product(*self.sets)
        else:
            raise TypeError("Not all constituent sets are iterable")

    @property
    def _measure(self):
        measure = 1
        for set in self.sets:
            measure *= set.measure
        return measure

class RealSet(Set, EvalfMixin):
    """
    A set of real values
    """
    is_real = True

class CountableSet(Set):
    """
    Represents a set of countable numbers such as {1, 2, 3, 4} or {1, 2, 3, ...}
    """
    is_iterable = True

    @property
    def _measure(self):
        return 0

    def __iter__(self):
        raise NotImplementedError("Iteration not yet implemented")

class Interval(RealSet):
    """
    Represents a real interval as a Set.

    Usage:
        Returns an interval with end points "start" and "end".

        For left_open=True (default left_open is False) the interval
        will be open on the left. Similarly, for right_open=True the interval
        will be open on the right.

    Examples
    ========

    >>> from sympy import Symbol, Interval, sets

    >>> Interval(0, 1)
    [0, 1]
    >>> Interval(0, 1, False, True)
    [0, 1)

    >>> a = Symbol('a', real=True)
    >>> Interval(0, a)
    [0, a]

    Notes
    =====
    - Only real end points are supported
    - Interval(a, b) with a > b will return the empty set
    - Use the evalf() method to turn an Interval into an mpmath
      'mpi' interval instance

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Interval_(mathematics)
    """
    is_Interval = True

    def __new__(cls, start, end, left_open=False, right_open=False):

        start = _sympify(start)
        end = _sympify(end)

        # Only allow real intervals (use symbols with 'is_real=True').
        if not start.is_real or not end.is_real:
            raise ValueError("Only real intervals are supported")

        # Make sure that the created interval will be valid.
        if end.is_comparable and start.is_comparable:
            if end < start:
                return S.EmptySet

        if end == start and (left_open or right_open):
            return S.EmptySet
        if end == start and not (left_open or right_open):
            return FiniteSet(end)

        # Make sure infinite interval end points are open.
        if start == S.NegativeInfinity:
            left_open = True
        if end == S.Infinity:
            right_open = True

        return Basic.__new__(cls, start, end, left_open, right_open)

    @property
    def start(self):
        """
        The left end point of 'self'.

        This property takes the same value as the 'inf' property.

        >>> from sympy import Interval

        >>> Interval(0, 1).start
        0

        """
        return self._args[0]

    _inf = left = start

    @property
    def end(self):
        """
        The right end point of 'self'.

        This property takes the same value as the 'sup' property.

        >>> from sympy import Interval

        >>> Interval(0, 1).end
        1

        """
        return self._args[1]

    _sup = right = end

    @property
    def left_open(self):
        """
        True if 'self' is left-open.

        >>> from sympy import Interval

        >>> Interval(0, 1, left_open=True).left_open
        True
        >>> Interval(0, 1, left_open=False).left_open
        False

        """
        return self._args[2]

    @property
    def right_open(self):
        """
        True if 'self' is right-open.

        >>> from sympy import Interval

        >>> Interval(0, 1, right_open=True).right_open
        True
        >>> Interval(0, 1, right_open=False).right_open
        False

        """
        return self._args[3]

    def _intersect(self, other):
        # We only know how to intersect with other intervals
        if not other.is_Interval:
            return None
        # We can't intersect [0,3] with [x,6] -- we don't know if x>0 or x<0
        if not self._is_comparable(other):
            return None

        empty = False

        if self.start <= other.end and other.start <= self.end:
            # Get topology right.
            if self.start < other.start:
                start = other.start
                left_open = other.left_open
            elif self.start > other.start:
                start = self.start
                left_open = self.left_open
            else:
                start = self.start
                left_open = self.left_open or other.left_open

            if self.end < other.end:
                end = self.end
                right_open = self.right_open
            elif self.end > other.end:
                end = other.end
                right_open = other.right_open
            else:
                end = self.end
                right_open = self.right_open or other.right_open

            if end - start == 0 and (left_open or right_open):
                empty = True
        else:
            empty = True

        if empty:
            return S.EmptySet

        return self.__class__(start, end, left_open, right_open)

    @property
    def _complement(self):
        a = Interval(S.NegativeInfinity, self.start, True, not self.left_open)
        b = Interval(self.end, S.Infinity, not self.right_open, True)
        return Union(a, b)

    def _contains(self, other):
        if self.left_open:
            expr = other > self.start
        else:
            expr = other >= self.start

        if self.right_open:
            expr = And(expr, other < self.end)
        else:
            expr = And(expr, other <= self.end)

        return expr

    @property
    def _measure(self):
        return self.end - self.start

    def to_mpi(self, prec=53):
        return mpi(mpf(self.start.evalf(prec)), mpf(self.end.evalf(prec)))

    def _eval_evalf(self, prec):
        return Interval(self.left.evalf(), self.right.evalf(),
            left_open=self.left_open, right_open=self.right_open)

    def _is_comparable(self, other):
        is_comparable = self.start.is_comparable
        is_comparable &= self.end.is_comparable
        is_comparable &= other.start.is_comparable
        is_comparable &= other.end.is_comparable

        return is_comparable

    @property
    def is_left_unbounded(self):
        """Return ``True`` if the left endpoint is negative infinity. """
        return self.left is S.NegativeInfinity or self.left == Float("-inf")

    @property
    def is_right_unbounded(self):
        """Return ``True`` if the right endpoint is positive infinity. """
        return self.right is S.Infinity or self.right == Float("+inf")

    def as_relational(self, symbol):
        """Rewrite an interval in terms of inequalities and logic operators. """
        from sympy.core.relational import Lt, Le

        if not self.is_left_unbounded:
            if self.left_open:
                left = Lt(self.start, symbol)
            else:
                left = Le(self.start, symbol)

        if not self.is_right_unbounded:
            if self.right_open:
                right = Lt(symbol, self.right)
            else:
                right = Le(symbol, self.right)
        if self.is_left_unbounded and self.is_right_unbounded:
            return True # XXX: Contained(symbol, Floats)
        elif self.is_left_unbounded:
            return right
        elif self.is_right_unbounded:
            return left
        else:
            return And(left, right)

class Union(Set):
    """
    Represents a union of sets as a Set.

    Examples
    ========

        >>> from sympy import Union, Interval

        >>> Union(Interval(1, 2), Interval(3, 4))
        [1, 2] U [3, 4]

        The Union constructor will always try to merge overlapping intervals,
        if possible. For example:

        >>> Union(Interval(1, 2), Interval(2, 3))
        [1, 3]

    See Also
    ========
    Intersection

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Union_(set_theory)
    """
    is_Union = True

    def __new__(cls, *args):
        # Flatten out Iterators and Unions to form one list of sets
        args = list(args)
        def flatten(arg):
            if arg == S.EmptySet:
                return []
            if isinstance(arg, Set):
                if arg.is_Union:
                    return sum(map(flatten, arg.args), [])
                else:
                    return [arg]
            if is_flattenable(arg): # and not isinstance(arg, Set) (implicit)
                return sum(map(flatten, arg), [])
            raise TypeError("Input must be Sets or iterables of Sets")
        args = flatten(args)
        if len(args) == 0:
            return S.EmptySet

        # Only real parts? Return a RealUnion
        if all(arg.is_real for arg in args):
            return RealUnion(args)

        # Lets find and merge real elements if we have them
        # Separate into finite, real and other sets

        finite_set = sum([s for s in args if s.is_FiniteSet], S.EmptySet)
        real_sets = [s for s in args if s.is_real]
        other_sets = [s for s in args if not s.is_FiniteSet and not s.is_real]

        # Separate finite_set into real and other part
        real_finite = RealFiniteSet(i for i in finite_set if i.is_real)
        other_finite = FiniteSet(i for i in finite_set if not i.is_real)

        # Merge real part of set
        real_union = RealUnion(real_sets+[real_finite])

        if not real_union: # Real part was empty
            sets = other_sets + [other_finite]
        elif real_union.is_FiniteSet: # Real part was just a FiniteSet
            sets = other_sets + [real_union+other_finite]
        elif real_union.is_Interval: # Real part was just an Interval
            sets = [real_union] + other_sets + [other_finite]
        # If is_RealUnion then separate
        elif real_union.is_Union and real_union.is_real:
            intervals = [s for s in real_union.args if s.is_Interval]
            finite_set = sum([s for s in real_union.args if s.is_FiniteSet] +
                [other_finite], S.EmptySet) # Join FiniteSet back together
            sets = intervals + [finite_set] + other_sets

        # Clear out Empty Sets
        sets = [set for set in sets if set != S.EmptySet]

        # If a single set is left over, don't create a new Union object but
        # rather return the single set.
        if len(sets) == 1:
            return sets[0]

        return Basic.__new__(cls, *sets)

    @property
    def _inf(self):
        # We use Min so that sup is meaningful in combination with symbolic
        # interval end points.
        from sympy.functions.elementary.miscellaneous import Min
        return Min(*[set.inf for set in self.args])

    @property
    def _sup(self):
        # We use Max so that sup is meaningful in combination with symbolic
        # end points.
        from sympy.functions.elementary.miscellaneous import Max
        return Max(*[set.sup for set in self.args])

    @property
    def _complement(self):
        # De Morgan's formula.
        complement = self.args[0].complement
        for set in self.args[1:]:
            complement = complement.intersect(set.complement)
        return complement

    def _contains(self, other):
        or_args = [the_set.contains(other) for the_set in self.args]
        return Or(*or_args)

    @property
    def _measure(self):
        # Measure of a union is the sum of the measures of the sets minus
        # the sum of their pairwise intersections plus the sum of their
        # triple-wise intersections minus ... etc...

        # Sets is a collection of intersections and a set of elementary
        # sets which made up those interections (called "sos" for set of sets)
        # An example element might of this list might be:
        #    ( {A,B,C}, A.intersect(B).intersect(C) )

        # Start with just elementary sets (  ({A}, A), ({B}, B), ... )
        # Then get and subtract (  ({A,B}, (A int B), ... ) while non-zero
        sets = [(FiniteSet(s), s) for s in self.args]
        measure = 0
        parity = 1
        while sets:
            # Add up the measure of these sets and add or subtract it to total
            measure += parity * sum(inter.measure for sos, inter in sets)

            # For each intersection in sets, compute the intersection with every
            # other set not already part of the intersection.
            sets = ((sos + FiniteSet(newset), newset.intersect(intersection))
                    for sos, intersection in sets for newset in self.args
                    if newset not in sos)

            # Clear out sets with no measure
            sets = [(sos, inter) for sos, inter in sets if inter.measure != 0]

            # Clear out duplicates
            sos_list = []
            sets_list = []
            for set in sets:
                if set[0] in sos_list:
                    continue
                else:
                    sos_list.append(set[0])
                    sets_list.append(set)
            sets = sets_list

            # Flip Parity - next time subtract/add if we added/subtracted here
            parity *= -1
        return measure

    def as_relational(self, symbol):
        """Rewrite a Union in terms of equalities and logic operators. """
        return Or(*[set.as_relational(symbol) for set in self.args])

    @property
    def is_iterable(self):
        return all(arg.is_iterable for arg in self.args)


class Intersection(Set):
    """
    Represents an untersection of sets as a Set.

    Examples
    ========

        >>> from sympy import Intersection, Interval

        >>> Intersection(Interval(1, 3), Interval(2, 4))
        [2, 3]

        We often use the .intersect method

        >>> Interval(1,3).intersect(Interval(2,4))
        [2, 3]

    See Also
    ========
    Union

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Intersection_(set_theory)
    """
    is_Intersection = True

    def __new__(cls, *args, **kwargs):
        evaluate = kwargs.get('evaluate', True)

        # flatten inputs to merge intersections and iterables
        args = list(args)
        def flatten(arg):
            if isinstance(arg, Set):
                if arg.is_Intersection:
                    return sum(map(flatten, arg.args), [])
                else:
                    return [arg]
            if is_flattenable(arg): # and not isinstance(arg, Set) (implicit)
                return sum(map(flatten, arg), [])
            raise TypeError("Input must be Sets or iterables of Sets")
        args = flatten(args)

        # Intersection of no sets is everything
        if len(args)==0:
            return S.UniversalSet

        # Reduce sets using known rules
        if evaluate:
            return Intersection.reduce(args)

        return Basic.__new__(cls, *args)

    @property
    def is_iterable(self):
        return any(arg.is_iterable for arg in self.args)

    @property
    def _inf(self):
        raise NotImplementedError()

    @property
    def _sup(self):
        raise NotImplementedError()

    @property
    def _complement(self):
        raise NotImplementedError()

    def _contains(self, other):
        from sympy.logic.boolalg import And
        return And(*[set.contains(other) for set in self.args])

    def __iter__(self):
        for s in self.args:
            if s.is_iterable:
                other_sets = set(self.args) - set((s,))
                other = Intersection(other_sets, evaluate=False)
                return (x for x in s if x in other)

        raise ValueError("None of the constituent sets are iterable")

    @staticmethod
    def reduce(args):
        """
        Simplify an intersection using known rules

        We first start with global rules like
        'if any empty sets return empty set' and 'distribute any unions'

        Then we iterate through all pairs and ask the constituent sets if they
        can simplify themselves with any other constituent
        """

        # ===== Global Rules =====
        # If any EmptySets return EmptySet
        if any(s.is_EmptySet for s in args):
            return S.EmptySet

        # If any FiniteSets see which elements of that finite set occur within
        # all other sets in the intersection
        for s in args:
            if s.is_FiniteSet:
                return s.__class__(x for x in s
                        if all(x in other for other in args))

        # If any of the sets are unions, return a Union of Intersections
        for s in args:
            if s.is_Union:
                other_sets = set(args) - set((s,))
                other = Intersection(other_sets)
                return Union(Intersection(arg, other) for arg in s.args)

        # At this stage we are guaranteed not to have any
        # EmptySets, FiniteSets, or Unions in the intersection

        # ===== Pair-wise Rules =====
        # Here we depend on rules built into the constituent sets
        args = set(args)
        new_args = True
        while(new_args):
            for s in args:
                new_args = False
                for t in args - set((s,)):
                    new_set = s._intersect(t)
                    # This returns None if s does not know how to intersect
                    # with t. Returns the newly intersected set otherwise
                    if new_set is not None:
                        new_args = (args - set((s, t))).union(set((new_set, )))
                        break
                if new_args:
                    args = new_args
                    break

        if len(args)==1:
            return args.pop()
        else:
            return Intersection(args, evaluate=False)

class RealUnion(Union, RealSet):
    """
    Represents a union of Real Sets (Intervals, RealFiniteSets)

    This class should only be used internally.
    Please make unions with Union class.

    See Union for details
    """
    def __new__(cls, *args):

        intervals, finite_sets, other_sets = [], [], []
        args = list(args)
        for arg in args:

            if isinstance(arg, Set):
                if arg == S.EmptySet:
                    continue
                elif arg.is_Union:
                    args += arg.args
                elif arg.is_FiniteSet:
                    finite_sets.append(arg)
                elif arg.is_Interval:
                    intervals.append(arg)
                else:
                    other_sets.append(arg)
            elif is_flattenable(arg):
                args += arg
            else:
                raise TypeError("%s: Not a set or iterable of sets"%arg)

        # Sort intervals according to their infimum
        intervals.sort(key=lambda i: i.start)

        # Merge comparable overlapping intervals
        i = 0
        while i < len(intervals) - 1:
            cur = intervals[i]
            next = intervals[i + 1]

            merge = False
            if cur._is_comparable(next):
                if next.start < cur.end:
                    merge = True
                elif next.start == cur.end:
                    # Must be careful with boundaries.
                    merge = not(next.left_open and cur.right_open)

            if merge:
                if cur.start == next.start:
                    left_open = cur.left_open and next.left_open
                else:
                    left_open = cur.left_open

                if cur.end < next.end:
                    right_open = next.right_open
                    end = next.end
                elif cur.end > next.end:
                    right_open = cur.right_open
                    end = cur.end
                else:
                    right_open = cur.right_open and next.right_open
                    end = cur.end

                intervals[i] = Interval(cur.start, end, left_open, right_open)
                del intervals[i + 1]
            else:
                i += 1

        # Collect all elements in the finite sets not in any interval
        if finite_sets:
            # Merge Finite Sets
            finite_set = sum(finite_sets, S.EmptySet)

            # Close open intervals if boundary is in finite_set
            for num, i in enumerate(intervals):
                closeLeft = i.start in finite_set if i.left_open else False
                closeRight = i.end in finite_set if i.right_open else False
                if ((closeLeft and i.left_open)
                        or (closeRight and i.right_open)):
                    intervals[num] = Interval(i.start, i.end,
                            not closeLeft, not closeRight)

            # All elements in finite_set not in any interval
            finite_complement = FiniteSet(
                    el for el in finite_set
                    if not el.is_number
                    or not any(el in i for i in intervals))
            if len(finite_complement)>0: # Anything left?
                other_sets.append(finite_complement)

        # Clear out empty sets
        sets = [set for set in (intervals + other_sets) if set]

        # If nothing is there then return the empty set
        if not sets:
            return S.EmptySet

        # If a single set is left over, don't create a new Union object but
        # rather return the single set.
        if len(sets) == 1:
            return sets[0]

        return Basic.__new__(cls, *sets)

    def _eval_evalf(self, prec):
        return RealUnion(set.evalf() for set in self.args)

    def __iter__(self):
        import itertools
        if all(set.is_iterable for set in self.args):
            return itertools.chain(*(iter(arg) for arg in self.args))
        else:
            raise TypeError("Not all constituent sets are iterable")

class EmptySet(Set):
    """
    Represents the empty set. The empty set is available as a singleton
    as S.EmptySet.

    Examples
    ========

        >>> from sympy import S, Interval

        >>> S.EmptySet
        EmptySet()

        >>> Interval(1, 2).intersect(S.EmptySet)
        EmptySet()

    See Also
    ========
    UniversalSet

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Empty_set
    """
    __metaclass__ = Singleton
    is_EmptySet = True

    def _intersect(self, other):
        return S.EmptySet

    @property
    def _complement(self):
        return S.UniversalSet

    @property
    def _measure(self):
        return 0

    def _contains(self, other):
        return False

    def as_relational(self, symbol):
        return False

    def __len__(self):
        return 0

    def union(self, other):
        return other

    def __iter__(self):
        return iter([])

class UniversalSet(Set):
    """
    Represents the set of all things.
    The universal set is available as a singleton as S.UniversalSet

    Examples
    ========

        >>> from sympy import S, Interval

        >>> S.UniversalSet
        UniversalSet()

        >>> Interval(1, 2).intersect(S.UniversalSet)
        [1, 2]

    See Also
    ========
    EmptySet

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Universal_set
    """

    __metaclass__ = Singleton
    is_UniversalSet = True

    def _intersect(self, other):
        return other

    @property
    def _complement(self):
        return S.EmptySet

    @property
    def _measure(self):
        return S.Infinity

    def _contains(self, other):
        return True

    def as_relational(self, symbol):
        return True

    def union(self, other):
        return self

class FiniteSet(CountableSet):
    """
    Represents a finite set of discrete numbers

    Examples
    ========

        >>> from sympy import Symbol, FiniteSet, sets

        >>> FiniteSet(1, 2, 3, 4)
        {1, 2, 3, 4}
        >>> 3 in FiniteSet(1, 2, 3, 4)
        True

    References
    ==========

    .. [1] http://en.wikipedia.org/wiki/Finite_set
    """
    is_FiniteSet = True

    def __new__(cls, *args):
        def flatten(arg):
            if is_flattenable(arg):
                return sum(map(flatten, arg), [])
            return [arg]
        args = flatten(list(args))

        args = map(sympify, args)

        if len(args) == 0:
            return EmptySet()

        try:
            if all([arg.is_real and arg.is_number for arg in args]):
                cls = RealFiniteSet
        except AttributeError:
            pass

        elements = frozenset(args)
        obj = Basic.__new__(cls, elements)
        obj.elements = elements
        return obj

    @property
    def args(self):
        return tuple(self.elements)

    def __iter__(self):
        return self.elements.__iter__()

    def _intersect(self, other):
        if isinstance(other, self.__class__):
            return self.__class__(*(self.elements & other.elements))
        return self.__class__(el for el in self if el in other)

    def union(self, other):
        """
        Returns the union of 'self' and 'other'.

        As a shortcut it is possible to use the '+' operator:

        >>> from sympy import FiniteSet, Interval, Symbol

        >>> FiniteSet(0, 1).union(FiniteSet(2, 3))
        {0, 1, 2, 3}
        >>> FiniteSet(Symbol('x'), 1, 2) + FiniteSet(2, 3)
        {1, 2, 3, x}
        >>> Interval(1, 2, True, True) + FiniteSet(2, 3)
        (1, 2] U {3}

        Similarly it is possible to use the '-' operator for set
        differences:

        >>> FiniteSet(Symbol('x'), 1, 2) - FiniteSet(2, 3)
        {1, x}
        >>> Interval(1, 2) - FiniteSet(2, 3)
        [1, 2)

        """
        if other == S.EmptySet:
            return self
        if other.is_FiniteSet:
            return FiniteSet(*(self.elements | other.elements))
        return Union(self, other) # Resort to default

    def _contains(self, other):
        """
        Tests whether an element, other, is in the set.

        Relies on Python's set class. This tests for object equality
        All inputs are sympified

        >>> from sympy import FiniteSet

        >>> 1 in FiniteSet(1, 2)
        True
        >>> 5 in FiniteSet(1, 2)
        False

        """
        return other in self.elements

    @property
    def _inf(self):
        from sympy.functions.elementary.miscellaneous import Min
        return Min(*self)

    @property
    def _sup(self):
        from sympy.functions.elementary.miscellaneous import Max
        return Max(*self)

    def __len__(self):
        return len(self.elements)

    def __sub__(self, other):
        return FiniteSet(el for el in self if el not in other)

    def as_relational(self, symbol):
        """Rewrite a FiniteSet in terms of equalities and logic operators. """
        from sympy.core.relational import Eq
        return Or(*[Eq(symbol, elem) for elem in self])

    @property
    def is_real(self):
        return all(el.is_real for el in self)

    def compare(self, other):
        return (hash(self) - hash(other))

class RealFiniteSet(FiniteSet, RealSet):
    """
    A FiniteSet with all elements Real Numbers.

    Allows for good integration with Intervals.

    This class for internal use only. Use FiniteSet to create a RealFiniteSet

    See Also
    ========
    FiniteSet
    """

    def _eval_evalf(self, prec):
        return RealFiniteSet(elem.evalf(prec) for elem in self)

    @property
    def _complement(self):
        """
        The complement of a real finite set is the Union of open Intervals
        between the elements of the set.

        >>> from sympy import FiniteSet
        >>> FiniteSet(1, 2, 3).complement
        (-oo, 1) U (1, 2) U (2, 3) U (3, oo)


        """
        if not all(elem.is_number for elem in self.elements):
            raise ValueError("%s: Complement not defined for symbolic inputs"
                    %self)
        sorted_elements = sorted(list(self.elements))

        intervals = [] # Build up a list of intervals between the elements
        intervals += [Interval(S.NegativeInfinity,sorted_elements[0],True,True)]
        for a, b in zip(sorted_elements[:-1], sorted_elements[1:]):
            intervals.append(Interval(a, b, True, True)) # open intervals
        intervals.append(Interval(sorted_elements[-1], S.Infinity, True, True))
        return Union(*intervals)

    def as_relational(self, symbol):
        """Rewrite a FiniteSet in terms of equalities and logic operators. """
        from sympy.core.relational import Eq
        return Or(*[Eq(symbol, elem) for elem in self])

genclass = (1 for i in xrange(2)).__class__
def is_flattenable(obj):
    """
    Checks that an argument to a Set constructor should be flattened
    """
    return obj.__class__ in [list, set, genclass]
