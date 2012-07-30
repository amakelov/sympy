from sympy.combinatorics import Permutation
from sympy.core import Basic
from sympy.combinatorics.permutations import perm_af_mul, \
 _new_from_array_form, perm_af_commutes_with, perm_af_invert, perm_af_muln
from random import randrange, choice
from sympy.functions.combinatorial.factorials import factorial
from math import log
from sympy.ntheory import isprime, sieve
from sympy.combinatorics.util import _check_cycles_alt_sym,\
_distribute_gens_by_base, _orbits_transversals_from_bsgs,\
_handle_precomputed_bsgs, _base_ordering, _strong_gens_from_distr, _strip,\
_insert_point_in_base

def _smallest_change(h, alpha):
    """
    find the smallest point not fixed by `h`
    """
    for i in range(alpha, len(h)):
        if h[i] != i:
            return i

class _Vertex(object):
    """
    vertex of JGraph

    neighbor list of neighbor vertices
    perm     list of permutations
    index_neighbor list of index position of vertices in neighbor
    if vertex j is a neighbor of vertex i, then
       vertex[i].index_neighbor[ vertex[i].neighbor[j] ] = j
    if vertex j is not a neighbor of vertex i,
    vertex[i].index_neighbor[j] = -1
    n size of permutation

    """
    def __init__(self, n):

      self.neighbor = []
      self.perm = []
      self.index_neighbor = [-1]*n

class _JGraph(object):
    """
    Jerrum graph

    vertex   vertices of the Jerrum graph for permutation group G < S(n);
    vertex[i] i-th vertex, with `i` in range(n)
    jg       array of Jerrums generators (edges of the graph)
    jgs number of occupied entries of jg
    freejg   stack of slots of jg. freejg[i] points to the
             i-th free position of jg
    To a directed edge (i, j) between vertices i, j
    it is associated the index of a permutation `g` satisfying
    g[i] = j
    g = jg[vertex[i].perm[vertex[i].index_neighbor[j]]]
      = jg[vertex[j].perm[vertex[j].index_neighbor[i]]]

    cycle  list of indices of vertices used to identify cycles
    G Permutation group
    n size of permutation
    r number of generators
    """
    def __init__(self, G):
        n = G._degree
        self.vertex = [_Vertex(n) for i in range(n)]
        self.gens = [p.array_form for p in G._generators]
        self.jg = [None]*n
        self.jgs = 0
        self.freejg = []
        self.cycle = []
        self.G = G
        self.n = G._degree
        self.r = G._r
        self.idn = range(n)

    def find_cycle(self, v, v1, v2, prev):
        """
        find if there is a cycle

        v      vertex from which start searching a cycle
        v1, v2 vertices through which the cycle must go
        prev   previous vertex
        """
        cycle = self.cycle
        neighbor = self.vertex[v].neighbor
        if v1 in neighbor:
            if v1 != prev:
                return True
        if v2 in neighbor:
            if v2 != prev:
                cycle.append(v2)
                if self.find_cycle(v2, v1, v2, v):
                    return True
                cycle.pop()
        for u in neighbor:
            if u != prev:
                cycle.append(u)
                if self.find_cycle(u, v1, v2, v):
                    return True
                cycle.pop()
        return False

    def insert_edge(self, g, i, ig):
        """
        insert edge (permutation g) moving i to ig (i < ig)
        """
        vertex = self.vertex
        self.jgs += 1
        jgslot = self.freejg.pop() # the last free generator place
        self.jg[jgslot] = g
        nn = len(vertex[i].neighbor)
        vertex[i].neighbor.append(ig)
        vertex[i].perm.append(jgslot)
        vertex[i].index_neighbor[ig] = nn
        nn = len(vertex[ig].neighbor)
        vertex[ig].neighbor.append(i)
        vertex[ig].perm.append(jgslot)
        vertex[ig].index_neighbor[i] = nn

    def remove_edge(self, i, ig):
        """
        remove edge from i to ig
        """
        vertex = self.vertex
        # remove the permutation labelling this edge
        self.jgs -= 1
        jgslot = vertex[i].perm[ vertex[i].index_neighbor[ig] ]
        self.jg[jgslot] = None
        self.freejg.append(jgslot) # now we gained a free place

        for i1, i2 in ((i, ig), (ig, i)):
            v = vertex[i1]
            j0 = v.index_neighbor[i2]
            v.neighbor.pop(j0)
            v.perm.pop(j0)
            # the index of the vertices >= j0  in vertex[i] has changed
            for j in range(j0, len(v.neighbor)):
                v.index_neighbor[ v.neighbor[j] ] = j
            v.index_neighbor[ig] = -1

    def insert(self, g, alpha):
        """
        insert permutation `g` in stabilizer chain at point alpha
        """
        n = len(g)
        if not g == self.idn:
            vertex = self.vertex
            jg = self.jg
            i = _smallest_change(g, alpha)
            ig = g[i]
            nn = vertex[i].index_neighbor[ig]
            if nn >= 0:  # if ig is already neighbor of i
                jginn = jg[vertex[i].perm[nn]]
                if g != jginn:
                    # cycle consisting of two edges;
                    # replace jginn by g and insert h = g**-1*jginn
                    g1 = perm_af_invert(g)
                    h = perm_af_mul(g1, jginn)
                    jg[ vertex[i].perm[nn] ] = g
                    self.insert(h, alpha)
            else:  # new edge
                self.insert_edge(g, i, ig)
                self.cycle = [i]
                if self.find_cycle(i, i, ig, -1):
                    cycle = self.cycle
                    cycle.append(cycle[0])
                    # find the smallest point (vertex) of the cycle
                    minn = min(cycle)
                    cmin = cycle.index(minn)

                    # now walk around the cycle starting from the smallest
                    # point, and multiply around the cycle to obtain h
                    # satisfying h[cmin] = cmin
                    ap = []
                    for c in range(cmin, len(cycle)-1) + range(cmin):
                        i = cycle[c]
                        j = cycle[c+1]
                        nn = vertex[i].index_neighbor[j]
                        p = jg[ vertex[i].perm[nn] ]

                        if i > j:
                            p = perm_af_invert(p)
                        ap.append(p)
                    ap.reverse()
                    h = perm_af_muln(*ap)
                    self.remove_edge(cycle[cmin], cycle[cmin + 1])
                    self.insert(h, alpha)

    def schreier_tree(self, alpha, gen):
        """
        traversal of the orbit of alpha

        Compute a traversal of the orbit of alpha, storing the values
        in G._coset_repr; G._coset_repr[i][alpha] = i if i belongs
        to the orbit of alpha.
        """
        G = self.G
        G._coset_repr[alpha] = gen
        G._coset_repr_n += 1
        genv = self.gens[:self.r]
        h = 0
        r = self.r
        stg = [gen]
        sta = [alpha]
        pos = [0]*self.n
        while 1:
            # backtrack when finished iterating over generators
            if pos[h] >= r:
                if h == 0:
                    return
                pos[h] = 0
                h -= 1
                sta.pop()
                stg.pop()
                continue
            g = genv[pos[h]]
            pos[h] += 1
            alpha = sta[-1]
            ag = g[alpha]

            if G._coset_repr[ag] == None:
                gen1 = perm_af_mul(g, stg[-1])
                G._coset_repr[ag] = gen1
                G._coset_repr_n += 1
                sta.append(ag)
                stg.append(gen1)
                h += 1

    def jerrum_filter(self, alpha, cri):
        """
        filter the generators of the stabilizer subgroup G_alpha

        alpha point for which the stabilizer is computed

        cri[i] inverse of G._coset_repr[i] if `i` is not None

        Schreier lemma: the stabilizer subgroup G_alpha of G
        is generated by the schreier generators
        h = cosrep[ p2[i] ]**-1 * g[j] * cosrep[i]
        where j=0,..,len(gens)-1 and i=0,..,n-1, where n is the degree.
        Proof that h belongs to G_alpha:
        cosrep[k][alpha] = k for all k; cosrep[k]**-1[k] = alpha
        p1 = cosrep[i]; p2 = g[j]
        p3 = cosrep[ p2[i] ]; p3[alpha] = p2[i]
        p3**-1[p2[i] = alpha
        p3**-1[p2[p1[alpha]] = alpha, so h[alpha] = alpha

        Using Jerrum's filter one can reduce the len(gens)*n generators
        of G_alpha produced by the Schreier lemma to at most n-1

        Jerrum's filter:
        (see Cameron 'Permutation groups', page 22)
        _JGraph has n-1 vertices; the edges (i, j) are labelled by
        group elements `g` with j = imin(g) = min(i | g[i] != i);
        define m(graph) = sum(imin(g) for g in graph)

        At the beginning the graph has no edges, so it is
        an acyclic graph.
        Insert a group element `g` produced by the Schreier lemma;
        introduce in _JGraph an edge (imin(g), g[imin(g));
        if the graph contains a cycle,
        let `i0` be the smallest point in the cycle, and `h` the
        product of the group elements labelling the edges in the cycle,
        starting from `i0`; h[j] = j for j <= i0;
        modify it eliminating the edge (i0, g0[i0])
        in the cycle; one obtains a new acyclic graph with
        m(graph_new) > m(graph). `g0` can be expressed as a product
        of `h` and the other elements in the cycle.
        Then insert `h` in the graph, and so on.
        Since m < n**2, this process ends after
        a finite number of times, so in the end one remains
        with an acyclic graph, with at most n-1 edges and
        the same number of generators.
        """
        n = self.n
        r = self.r
        G = self.G
        gens = self.gens
        cosrep = G._coset_repr
        self.jgs = 0
        for j in range(n):
            self.jg[j] = None
        self.freejg = range(n)
        for i in range(n):
            self.vertex[i].neighbor = []
            self.vertex[i].perm = []
        for i in range(n):
            for j in range(n):
                self.vertex[i].index_neighbor[j] = -1

        for i in range(n):
            if cosrep[i] != None:
                p1 = cosrep[i]
                for j in range(r):
                    p2 = gens[j]
                    p3 = cri[ p2[i] ]
                    h = [p3[p2[k]] for k in p1]
                    self.insert(h, alpha)
        r = 0
        for j in range(n):
            if self.jg[j] != None:
                gens[r] = self.jg[j]
                r += 1
        self.r = r

class PermutationGroup(Basic):
    """
    The class defining a Permutation group.

    Permutation(generator_list) returns the permutation group
    generated by permutation_list.

    >>> from sympy.combinatorics.permutations import Permutation
    >>> from sympy.combinatorics.perm_groups import PermutationGroup
    >>> a = Permutation([0, 2, 1])
    >>> b = Permutation([1, 0, 2])
    >>> G = PermutationGroup([a, b])
    >>> G
    PermutationGroup([Permutation([0, 2, 1]), Permutation([1, 0, 2])])

    References
    ==========

    [1] Holt, D., Eick, B., O'Brien, E.
    "Handbook of computational group theory"

    [2] Seress, A.
    "Permutation group algorithms"

    [3] http://en.wikipedia.org/wiki/Schreier_vector

    [4] http://en.wikipedia.org/wiki/Nielsen_transformation
    #Product_replacement_algorithm

    [5] Frank Celler, Charles R.Leedham-Green, Scott H.Murray,
    Alice C.Niemeyer, and E.A.O'Brien. "Generating random
    elements of a finite group"

    [6] http://en.wikipedia.org/wiki/Block_%28permutation_group_theory%29

    [7] http://www.algorithmist.com/index.php/Union_Find

    [8] http://en.wikipedia.org/wiki/Multiply_transitive_group#Multiply_transitive_groups

    """

    def __new__(cls, *args, **kw_args):
        """
        The default constructor.
        """
        obj = Basic.__new__(cls, *args, **kw_args)
        obj._generators = args[0]
        obj._order = None
        obj._center = []
        obj._is_abelian = None
        obj._is_transitive = None
        obj._is_sym = None
        obj._is_alt = None
        obj._is_primitive = None
        obj._transitivity_degree = None
        obj._max_div = None
        size = len(args[0][0].array_form)
        obj._r = len(obj._generators)
        if not all(len(args[0][i].array_form)==size for i in xrange(1, len(args[0]))):
                raise ValueError("Permutation group size is not correct")
        obj._degree = size

        # these attributes are assigned after running schreier_sims
        obj._base = []
        obj._coset_repr = []
        obj._coset_repr_n = []
        obj._stabilizers_gens = []
        obj._strong_gens = []
        obj._basic_orbits = []
        obj._transversals = []

        # these attributes are assigned after running _random_pr_init
        obj._random_gens = []
        return obj

    def __mul__(self, other):
        """
        Return the direct product of two permutation groups as a permutation
        group.

        This implementation realizes the direct product by shifting
        the index set for the generators of the second group: so if we have
        G acting on n1 points and H acting on n2 points, G*H acts on n1+n2
        points.

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import CyclicGroup
        >>> G = CyclicGroup(5)
        >>> H = G*G
        >>> H
        PermutationGroup([Permutation([1, 2, 3, 4, 0, 5, 6, 7, 8, 9]),
        Permutation([0, 1, 2, 3, 4, 6, 7, 8, 9, 5])])
        >>> H.order()
        25

        """
        gens1 = [perm.array_form for perm in self.generators]
        gens2 = [perm.array_form for perm in other.generators]
        n1 = self.degree
        n2 = other.degree
        start = range(n1)
        end = range(n1, n1 + n2)
        for i in range(len(gens2)):
            gens2[i] = [x + n1 for x in gens2[i]]
        gens2 = [start + gen for gen in gens2]
        gens1 = [gen + end for gen in gens1]
        together = gens1 + gens2
        gens = [_new_from_array_form(x) for x in together]
        return PermutationGroup(gens)

    @property
    def degree(self):
        """
        Returns the size of the permutations in the group.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1,0])
        >>> G = PermutationGroup([a])
        >>> G.degree
        2

        """
        return self._degree

    @property
    def generators(self):
        """
        Returns the generators of the group in array form.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.generators
        [Permutation([0, 2, 1]), Permutation([1, 0, 2])]

        """
        return self._generators

    @property
    def strong_gens(self):
        """
        Return a strong generating set from the Schreier-Sims algorithm.

        A generating set `S = \{g_1, g_2, ..., g_t\}` for a permutation group
        `G` is a strong generating set relative to the sequence of points
        (referred to as a "base") `(b_1, b_2, ..., b_k)` if, for
        `1 \leq i \leq k` we have that the intersection of the pointwise
        stabilizer `G^{(i+1)} := G_{b_1, b_2, ..., b_i}` with `S` generates
        the pointwise stabilizer `G^{(i+1)}`. The concepts of a base and
        strong generating set and their applications are discussed in depth
        in [1],pp.87-89 and [2],pp.55-57.

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> D = DihedralGroup(4)
        >>> D.strong_gens
        [Permutation([1, 2, 3, 0]), Permutation([3, 2, 1, 0]),\
        Permutation([0, 3, 2, 1])]
        >>> D.base
        [0, 1]

        See Also
        ========

        base, basic_transversals, basic_orbits, basic_stabilizers

        """
        if self._strong_gens == []:
            self.schreier_sims()
        return self._strong_gens

    @property
    def base(self):
        """
        Return a base from the Schreier-Sims algorithm.

        For a permutation group `G`, a base is a sequence of points
        `B = (b_1, b_2, ..., b_k)` such that no element of `G` apart from the
        identity fixes all the points in `B`. The concepts of a base and
        strong generating set and their applications are discussed in depth
        in [1],pp.87-89 and [2],pp.55-57.

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import SymmetricGroup
        >>> S = SymmetricGroup(4)
        >>> S.base
        [0, 1, 2]

        See Also
        ========

        strong_gens, basic_transversals, basic_orbits, basic_stabilizers

        """
        if self._base == []:
            self.schreier_sims()
        return self._base

    @property
    def basic_transversals(self):
        """
        Return basic transversals relative to a base and strong generating set.

        The basic transversals are transversals of the basic orbits. They
        are provided as a list of dictionaries, each dictionary having
        keys - the elements of one of the basic orbits, and values - the
        corresponding transversal elements. See [1],pp.87-89 for more
        information.

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import AlternatingGroup
        >>> A = AlternatingGroup(4)
        >>> A.basic_transversals
        [{0: Permutation([0, 1, 2, 3]), 1: Permutation([1, 2, 0, 3]),\
        2: Permutation([2, 0, 1, 3]), 3: Permutation([3, 0, 2, 1])},\
        {1: Permutation([0, 1, 2, 3]), 2: Permutation([0, 2, 3, 1]),\
        3: Permutation([0, 3, 1, 2])}]

        See Also
        ========

        strong_gens, base, basic_orbits, basic_stabilizers

        """
        if self._transversals == []:
            self.schreier_sims()
        return self._transversals

    @property
    def basic_orbits(self):
        """
        Return the basic orbits relative to a base and strong generating set.

        If `(b_1, b_2, ..., b_k)` is a base for a group `G`, and
        `G^{(i)} = G_{b_1, b_2, ..., b_{i-1}}` is the `i`-th basic stabilizer
        (so that `G^{(1)} = G`), the `i`-th basic orbit relative to this base
        is the orbit of `b_i` under `G^{(i)}`. See [1],pp.87-89 for more
        information.

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import SymmetricGroup
        >>> S = SymmetricGroup(4)
        >>> S.basic_orbits
        [[0, 1, 2, 3], [1, 2, 3], [2, 3]]

        See Also
        ========

        base, strong_gens, basic_transversals, basic_stabilizers

        """
        if self._basic_orbits == []:
            self.schreier_sims()
        return self._basic_orbits

    @property
    def basic_stabilizers(self):
        """
        Return a chain of stabilizers relative to a base and strong generating
        set.

        The `i`-th basic stabilizer `G^{(i)}` relative to a base
        `(b_1, b_2, ..., b_k)` is `G_{b_1, b_2, ..., b_{i-1}}`. For more
        information, see [1],pp.87-89.

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import AlternatingGroup
        >>> A = AlternatingGroup(4)
        >>> A.schreier_sims()
        >>> A.base
        [0, 1]
        >>> A.basic_stabilizers
        [PermutationGroup([Permutation([1, 2, 0, 3]), Permutation([0, 2, 3, 1]), Permutation([0, 3, 1, 2])]), PermutationGroup([Permutation([0, 2, 3, 1]), Permutation([0, 3, 1, 2])])]

        See Also
        ========

        base, strong_gens, basic_orbits, basic_transversals

        """


        if self._coset_repr == []:
            self.schreier_sims()
        strong_gens = self._strong_gens
        base = self._base
        distr_gens = _distribute_gens_by_base(base, strong_gens)
        basic_stabilizers = []
        for gens in distr_gens:
            basic_stabilizers.append(PermutationGroup(gens))
        return basic_stabilizers

    @property
    def is_abelian(self):
        """
        Checks if the group is Abelian.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.is_abelian
        False
        >>> a = Permutation([0, 2, 1])
        >>> G = PermutationGroup([a])
        >>> G.is_abelian
        True

        """
        if self._is_abelian is not None:
            return self._is_abelian

        self._is_abelian = True
        gens = [p.array_form for p in self.generators]
        for x in gens:
            for y in gens:
                if y <= x:
                    continue
                if not perm_af_commutes_with(x, y):
                    self._is_abelian = False
                    return False
        return True

    def order(self):
        """
        return the order of the group

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.order()
        6

        """
        if self._order != None:
            return self._order
        if self._is_sym:
            n = self.degree
            self._order = factorial(n)
            return self._order
        if self._is_alt:
            n = self.degree
            self._order = factorial(n)/2
            return self._order
        self.schreier_sims()
        m = 1
        for x in self._coset_repr_n:
            m *= x
        return m

    def coset_repr(self):
        """
        Return the Schreier-Sims representation of the group.

        The Schreier-Sims representation is the list of the cosets of
        the chain of stabilizers, see schreier_sims.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.coset_repr()
        [[[0, 1, 2], [1, 0, 2], [2, 0, 1]], [[0, 1, 2], [0, 2, 1]]]

        """
        if not self._coset_repr:
            self.schreier_sims()
        return self._coset_repr

    def stabilizers_gens(self):
        """
        Schreier-Sims stabilizers generators

        Return the generators of the stabilizers chain in the
        Schreier-Sims representation.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.stabilizers_gens()
        [[0, 2, 1]]

        """

        if not self._coset_repr:
            self.schreier_sims()
        return self._stabilizers_gens

    def schreier_sims(self):
        """
        Schreier-Sims algorithm.

        It computes the generators of the stabilizers chain
        G > G_{b_1} > .. > G_{b1,..,b_r} > 1
        in which G_{b_1,..,b_i} stabilizes b_1,..,b_i,
        and the corresponding `s` cosets.
        An element of the group can be written univoquely
        as the product h_1*..*h_s.

        We use Jerrum's filter in our implementation of the
        Schreier-Sims algorithm. It runs in polynomial time.

        This implementation is a translation of the C++ implementation in
        http://www.m8j.net

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.schreier_sims()
        >>> G.stabilizers_gens()
        [[0, 2, 1]]
        >>> G.coset_repr()
        [[[0, 1, 2], [1, 0, 2], [2, 0, 1]], [[0, 1, 2], [0, 2, 1]]]

        """
        if self._coset_repr:
            return
        JGr = _JGraph(self)
        alpha = 0
        n = JGr.n
        self._order = 1
        coset_repr = []
        num_generators = []
        generators = []
        gen = range(n)
        base = {}
        JGr.gens += [None]*(n - len(JGr.gens))
        while 1:
            self._coset_repr_n = 0
            self._coset_repr = [None]*n
            JGr.schreier_tree(alpha, gen)
            cri = []
            for p in self._coset_repr:
                if not p:
                    cri.append(p)
                else:
                    cri.append(perm_af_invert(p))
            JGr.jerrum_filter(alpha, cri)
            if self._coset_repr_n > 1:
                base[alpha] = self._coset_repr_n
            self._order *= self._coset_repr_n
            coset_repr.append([p for p in self._coset_repr if p])
            d = {}
            for p in self._coset_repr:
                if p:
                    d[p[alpha]] = p
            num_generators.append(JGr.r)
            if JGr.r:
                generators.extend(JGr.gens[:JGr.r])
            if JGr.r <= 0:
                break
            alpha += 1
        self._coset_repr = coset_repr
        a = []
        for p in generators:
            if p not in a:
                a.append(p)
        self._stabilizers_gens = a

        i = len(JGr.gens) - 1
        while not JGr.gens[i]:
            i -= 1
        JGr.gens = JGr.gens[:i+1]
        self._base = base.keys()
        self._coset_repr_n = base.values()
        strong_gens = self.generators[:]
        for gen in self._stabilizers_gens:
            gen = Permutation(gen)
            if gen not in strong_gens:
                strong_gens.append(gen)
        self._strong_gens = strong_gens
        base_len = len(self._base)
        transversals = [None]*base_len
        basic_orbits = [None]*base_len
        for index in xrange(base_len):
            transversals[index] = {}
            base_point = self._base[index]
            trans = self._coset_repr[base_point][:]
            for el in trans:
                el = Permutation(el)
                orbit_member = el(base_point)
                transversals[index][orbit_member] = el
            basic_orbits[index] =\
            transversals[index].keys()
        self._transversals = transversals
        self._basic_orbits = basic_orbits

    def coset_decomposition(self, g):
        """
        Decompose `g` as h_0*...*h_{len(u)}

        The Schreier-Sims coset representation u of `G`
        gives a univoque decomposition of an element `g`
        as h_0*...*h_{len(u)}, where h_i belongs to u[i]

        Output: [h_0, .., h_{len(u)}] if `g` belongs to `G`
                False otherwise

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([[0, 1, 3, 7, 6, 4], [2, 5]])
        >>> b = Permutation([[0, 1, 3, 2], [4, 5, 7, 6]])
        >>> G = PermutationGroup([a, b])
        >>> c = Permutation([[0, 1, 2, 3, 4], [5, 6, 7]])
        >>> G.coset_decomposition(c)
        False
        >>> c = Permutation([[0, 6], [1, 7], [2, 4], [3, 5]])
        >>> G.coset_decomposition(c)
        [[6, 4, 2, 0, 7, 5, 3, 1], [0, 4, 1, 5, 2, 6, 3, 7], [0, 1, 2, 3, 4, 5, 6, 7]]
        >>> G.has_element(c)
        True

        """
        u = self.coset_repr()
        if isinstance(g, Permutation):
            g = g.array_form
        g1 = g
        n = len(u)
        a = []
        for i in range(n):
            x = g1[i]
            for h in u[i]:
                if h[i] == x:
                    a.append(h)
                    p2 = perm_af_invert(h)
                    g1 = perm_af_mul(p2, g1)
                    break
            else:
                return False
        if perm_af_muln(*a) == g:
            return a
        return False

    def coset_rank(self, g):
        """
        rank using Schreier-Sims representation

        The coset rank of `g` is the ordering number in which
        it appears in the lexicographic listing according to the
        coset decomposition, see coset_decomposition;
        the ordering is the same as in G.generate(method='coset').
        If `g` does not belong to the group it returns None

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([[0, 1, 3, 7, 6, 4], [2, 5]])
        >>> b = Permutation([[0, 1, 3, 2], [4, 5, 7, 6]])
        >>> G = PermutationGroup([a, b])
        >>> c = Permutation([[0, 1, 2, 3, 4], [5, 6, 7]])
        >>> G.coset_rank(c)
        >>> c = Permutation([[0, 6], [1, 7], [2, 4], [3, 5]])
        >>> G.coset_rank(c)
        40
        >>> G.coset_unrank(40, af=True)
        [6, 7, 4, 5, 2, 3, 0, 1]

        """
        u = self.coset_repr()
        if isinstance(g, Permutation):
            g = g.array_form
        g1 = g
        m = len(u)
        a = []

        un = self._coset_repr_n
        n = self.degree
        rank = 0
        base = [1]
        for i in un[m:0:-1]:
            base.append(base[-1]*i)
        base.reverse()

        a1 = [0]*m
        i1 = -1
        for i in self._base:
            i1 += 1
            x = g1[i]
            for j, h in enumerate(u[i]):
                if h[i] == x:
                    a.append(h)
                    a1[i] = j
                    rank += j*base[i1]
                    p2 = perm_af_invert(h)
                    g1 = perm_af_mul(p2, g1)
                    break
            else:
                return None
        if perm_af_muln(*a) == g:
            return rank
        return None

    def coset_unrank(self, rank, af=False):
        """
        unrank using Schreier-Sims representation

        coset_unrank is the inverse operation of coset_rank
        if 0 <= rank < order; otherwise it returns None.

        """
        u = self.coset_repr()
        if rank < 0 or rank >= self.order():
            return None
        un = self._coset_repr_n
        base = self._base
        m = len(u)
        nb = len(base)
        assert nb == len(un)
        v = [0]*m
        for i in range(nb-1, -1,-1):
            j = base[i]
            rank, c = divmod(rank, un[i])
            v[j] = c
        a = [u[i][v[i]] for i in range(m)]
        h = perm_af_muln(*a)
        if af:
            return h
        else:
            return _new_from_array_form(h)

    def random(self, af=False):
        """
        return a random group element

        """
        rank = randrange(self.order())
        return self.coset_unrank(rank, af)

    def has_element(self, g):
        """
        test if `g` belongs to G; see coset_decomposition

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1, 3])
        >>> b = Permutation([0, 2, 3, 1])
        >>> g = PermutationGroup([a, b])
        >>> g.has_element(Permutation([0, 1, 3, 2]))
        True
        >>> g.has_element(Permutation([1, 2, 3, 0]))
        False

        """
        return bool(self.coset_decomposition(g.array_form))

    def generate_dimino(self, af=False):
        """
        yield group elements using Dimino's algorithm

        If af == True it yields the array form of the permutations

        Reference:
        [1] The implementation of various algorithms for Permutation Groups in
        the Computer Algebra System: AXIOM, N.J. Doye, M.Sc. Thesis

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1, 3])
        >>> b = Permutation([0, 2, 3, 1])
        >>> g = PermutationGroup([a, b])
        >>> list(g.generate_dimino(af=True))
        [[0, 1, 2, 3], [0, 2, 1, 3], [0, 2, 3, 1], [0, 1, 3, 2], [0, 3, 2, 1], [0, 3, 1, 2]]

        """
        idn = range(self.degree)
        order = 0
        element_list = [idn]
        set_element_list = set([tuple(idn)])
        if af:
            yield idn
        else:
            yield _new_from_array_form(idn)
        gens = [p.array_form for p in self.generators]

        for i in xrange(len(gens)):
            # D elements of the subgroup G_i generated by gens[:i]
            D = element_list[:]
            N = [idn]
            while N:
                A = N
                N = []
                for a in A:
                    for g in gens[:i+1]:
                        ag = perm_af_mul(a, g)
                        if tuple(ag) not in set_element_list:
                            # produce G_i*g
                            for d in D:
                                order += 1
                                ap = perm_af_mul(d, ag)
                                if af:
                                    yield ap
                                else:
                                    p = _new_from_array_form(ap)
                                    yield p
                                element_list.append(ap)
                                set_element_list.add(tuple(ap))
                                N.append(ap)
        self._order = len(element_list)

    def generate_schreier_sims(self, af=False):
        """
        yield group elements using the Schreier-Sims representation

        If af = True it yields the array form of the permutations

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1, 3])
        >>> b = Permutation([0, 2, 3, 1])
        >>> g = PermutationGroup([a, b])
        >>> list(g.generate_schreier_sims(af=True))
        [[0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 3, 1], [0, 2, 1, 3], [0, 3, 2, 1], [0, 3, 1, 2]]

        """
        def get1(posmax):
            n = len(posmax) - 1
            for i in range(n,-1,-1):
                if posmax[i] != 1:
                    return i + 1
        n = self.degree
        u = self.coset_repr()
        # stg stack of group elements
        stg = [range(n)]
        # posmax[i] = len(u[i])
        posmax = [len(x) for x in u]
        n1 = get1(posmax)
        pos = [0]*n1
        posmax = posmax[:n1]
        h = 0
        while 1:
            # backtrack when finished iterating over coset
            if pos[h] >= posmax[h]:
                if h == 0:
                    raise StopIteration
                pos[h] = 0
                h -= 1
                stg.pop()
                continue
            p = perm_af_mul(stg[-1], u[h][pos[h]])
            pos[h] += 1
            stg.append(p)
            h += 1
            if h == n1:
                if af:
                    yield p
                else:
                    p1 = _new_from_array_form(p)
                    yield p1
                stg.pop()
                h -= 1

    def generate(self, method="coset", af=False):
        """
        return iterator to generate the elements of the group

        Iteration is done with one of these methods:
          method='coset'  using the Schreier-Sims coset representation
          method='dimino' using the Dimino method

        If af = True it yields the array form of the permutations

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1, 3])
        >>> b = Permutation([0, 2, 3, 1])
        >>> g = PermutationGroup([a, b])
        >>> list(g.generate(af=True))
        [[0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 3, 1], [0, 2, 1, 3], [0, 3, 2, 1], [0, 3, 1, 2]]

        """
        if method == "coset":
            return self.generate_schreier_sims(af)
        elif method == "dimino":
            return self.generate_dimino(af)
        else:
            raise ValueError('there is not this method')

    def orbit(self, alpha, action='tuples'):
        r"""
        Compute the orbit of alpha `\{g(\alpha) | g \in G\}` as a set.

        The time complexity of the algorithm used here is `O(|Orb|*r)` where
        `|Orb|` is the size of the orbit and `r` is the number of generators of
        the group. For a more detailed analysis, see [1], p.78, [2], pp.19-21.
        Here alpha can be a single point, or a list of points.

        If alpha is a single point, the ordinary orbit is computed.
        if alpha is a list of points, there are three available options:

        'union' - computes the union of the orbits of the points in the list
        'tuples' - computes the orbit of the list interpreted as an ordered
        tuple under the group action ( i.e., g((1,2,3)) = (g(1), g(2), g(3)) )
        'sets' - computes the orbit of the list interpreted as a sets

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.permutations import Permutation
        >>> a = Permutation([1,2,0,4,5,6,3])
        >>> G = PermutationGroup([a])
        >>> G.orbit(0)
        set([0, 1, 2])
        >>> G.orbit([0,4], 'union')
        set([0, 1, 2, 3, 4, 5, 6])

        See Also
        ========

        orbit_transversal

        """
        if not hasattr(alpha, '__getitem__'):
            alpha = [alpha]

        if len(alpha) == 1 or action == 'union':
            orb = alpha
            used = [False]*self.degree
            for el in alpha:
                used[el] = True
            gens = self.generators
            for b in orb:
                for gen in gens:
                    temp = gen(b)
                    if used[temp] == False:
                        orb.append(temp)
                        used[temp] = True
            return set(orb)
        if action == 'tuples':
            alpha = tuple(alpha)
            orb = [alpha]
            used = set([alpha])
            gens = self.generators
            for b in orb:
                for gen in gens:
                    temp = tuple([gen(x) for x in b])
                    if temp not in used:
                        orb.append(temp)
                        used.add(temp)
            return set(orb)
        if action == 'sets':
            alpha = frozenset(alpha)
            orb = [alpha]
            used = set([alpha])
            gens = self.generators
            for b in orb:
                for gen in gens:
                    temp = frozenset([gen(x) for x in b])
                    if temp not in used:
                        orb.append(temp)
                        used.add(temp)
            return set([tuple(x) for x in orb])

    def orbit_transversal(self, alpha, pairs=False):
        r"""
        Computes a transversal for the orbit of ``alpha`` as a set.

        For a permutation group `G`, a transversal for the orbit
        `Orb = \{g(\alpha) | g \in G\}` is a set
        `\{g_\beta | g_\beta(\alpha) = \beta\}` for `\beta \in Orb`.
        Note that there may be more than one possible transversal.
        If ``pairs`` is set to ``True``, it returns the list of pairs
        `(\beta, g_\beta)`. For a proof of correctness, see [1], p.79

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> G = DihedralGroup(6)
        >>> G.orbit_transversal(0)
        [Permutation([0, 1, 2, 3, 4, 5]), Permutation([1, 2, 3, 4, 5, 0]),
        Permutation([5, 4, 3, 2, 1, 0]), Permutation([2, 3, 4, 5, 0, 1]),
        Permutation([4, 3, 2, 1, 0, 5]), Permutation([3, 4, 5, 0, 1, 2])]

        See Also
        ========

        orbit

        """
        n = self.degree
        tr = [(alpha, _new_from_array_form(range(n)))]
        used = [False]*n
        used[alpha] = True
        gens = self.generators
        for pair in tr:
            for gen in gens:
                temp = gen(pair[0])
                if used[temp] == False:
                    tr.append((temp, gen*pair[1]))
                    used[temp] = True
        if pairs:
            return tr
        return [pair[1] for pair in tr]

    def orbits(self, rep=False):
        """
        compute the orbits of G;
        if rep=False it returns a list of sets
        else it returns a list of representatives of the orbits

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.orbits()
        [set([0, 1, 2])]
        >>> G.orbits(rep=True)
        [0]

        """
        n = self._degree
        s1 = set(range(n))
        orbs = []
        while s1:
            i = s1.pop()
            si = self.orbit(i)
            if rep:
                orbs.append(i)
            else:
                orbs.append(si)
            s1 -= si
        return orbs

    @property
    def is_transitive(self):
        """
        test if the group is transitive

        A group is transitive if it has a single orbit.

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([0, 2, 1, 3])
        >>> b = Permutation([2, 0, 1, 3])
        >>> G1 = PermutationGroup([a, b])
        >>> G1.is_transitive
        False
        >>> c = Permutation([2, 3, 0, 1])
        >>> G2 = PermutationGroup([a, c])
        >>> G2.is_transitive
        True

        """
        if self._is_transitive is not None:
            return self._is_transitive

        ans = len(self.orbit(0)) == self.degree
        self._is_transitive = ans
        return ans

    def stabilizer(self, alpha):
        r"""
        Returns the stabilizer subgroup of ``alpha``.

        The stabilizer of `\alpha` is the group `G_\alpha =
        \{g \in G | g(\alpha) = \alpha\}`.
        For a proof of correctness, see [1], p.79.

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> G = DihedralGroup(6)
        >>> G.stabilizer(5)
        PermutationGroup([Permutation([4, 3, 2, 1, 0, 5]),
        Permutation([0, 1, 2, 3, 4, 5])])

        See Also
        ========

        orbit

        """
        n = self.degree
        orb = [alpha]
        table = {alpha: _new_from_array_form(range(n))}
        used = [False]*n
        used[alpha] = True
        gens = self.generators
        stab_gens = []
        for b in orb:
            for gen in gens:
                temp = gen(b)
                if used[temp] == False:
                    gen_temp = gen*table[b]
                    orb.append(temp)
                    table[temp] = gen_temp
                    used[temp] = True
                else:
                    schreier_gen = (~table[temp])*gen*table[b]
                    if schreier_gen not in stab_gens:
                        stab_gens.append(schreier_gen)
        return PermutationGroup(list(stab_gens))

    def schreier_vector(self, alpha):
        """
        Computes the schreier vector for ``alpha``.

        The Schreier vector efficiently stores information
        about the orbit of ``alpha``. It can later be used to quickly obtain
        elements of the group that send ``alpha`` to a particular element
        in the orbit. Notice that the Schreier vector depends on the order
        in which the group generators are listed. For a definition, see [3].
        Since list indices start from zero, we adopt the convention to use
        "None" instead of 0 to signify that an element doesn't belong
        to the orbit.
        For the algorithm and its correctness, see [2], pp.78-80.

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.permutations import Permutation
        >>> a = Permutation([2,4,6,3,1,5,0])
        >>> b = Permutation([0,1,3,5,4,6,2])
        >>> G = PermutationGroup([a,b])
        >>> G.schreier_vector(0)
        [-1, None, 0, 1, None, 1, 0]

        See Also
        ========

        orbit

        """
        n = self.degree
        v = [None]*n
        v[alpha] = -1
        orb = [alpha]
        used = [False]*n
        used[alpha] = True
        gens = self.generators
        r = len(gens)
        for b in orb:
            for i in range(r):
                temp = gens[i](b)
                if used[temp] == False:
                    orb.append(temp)
                    used[temp] = True
                    v[temp] = i
        return v

    def orbit_rep(self, alpha, beta, schreier_vector=None):
        """
        Return a group element which sends ``alpha`` to ``beta``.

        If ``beta`` is not in the orbit of ``alpha``, the function returns
        ``False``. This implementation makes use of the schreier vector.
        For a proof of correctness, see [1], p.80

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import AlternatingGroup
        >>> G = AlternatingGroup(5)
        >>> G.orbit_rep(0,4)
        Permutation([4, 2, 3, 0, 1])

        See Also
        ========

        schreier_vector

        """
        if schreier_vector == None:
            schreier_vector = self.schreier_vector(alpha)
        if schreier_vector[beta] == None:
            return False
        n = self.degree
        u = _new_from_array_form(range(n))
        k = schreier_vector[beta]
        gens = self.generators
        while k != -1:
            u = u*gens[k]
            beta = (~gens[k])(beta)
            k = schreier_vector[beta]
        return u

    def is_normal(self, gr):
        """
        test if G=self is a normal subgroup of gr

        G is normal in gr if
        for each g2 in G, g1 in gr, g = g1*g2*g1**-1 belongs to G
        It is sufficient to check this for each g1 in gr.generator and
        g2 g2 in G.generator

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1, 2, 0])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G1 = PermutationGroup([a, Permutation([2, 0, 1])])
        >>> G1.is_normal(G)
        True

        """
        gens2 = [p.array_form for p in self.generators]
        gens1 = [p.array_form for p in gr.generators]
        for g1 in gens1:
            for g2 in gens2:
                p = perm_af_muln(g1, g2, perm_af_invert(g1))
                if not self.coset_decomposition(p):
                    return False
        return True

    def normal_closure(self, gens):
        """
        normal closure in self of a list gens2 of permutations

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1, 2, 0])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a, b])
        >>> G.order()
        6
        >>> G1 = G.normal_closure([a])
        >>> list(G1.generate(af=True))
        [[0, 1, 2], [1, 2, 0], [2, 0, 1]]

        """
        G2 = PermutationGroup(gens)
        if G2.is_normal(self):
            return G2
        gens1 = [p.array_form for p in self.generators]
        b = 0
        while not b:
            gens2 = [p.array_form for p in G2.generators]
            b = 1
            for g1 in gens1:
                if not b:
                    break
                for g2 in gens2:
                    p = perm_af_muln(g1, g2, perm_af_invert(g1))
                    p = Permutation(p)
                    if not G2.has_element(p):
                        gens2 = G2.generators + [p]
                        G2 = PermutationGroup(gens2)
                        b = 0
                        break

        return G2

    def __eq__(self, gr):
        """
        test if two groups have the same elements

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = [[1,2,0,3,4,5], [1,0,2,3,4,5], [2,1,0,3,4,5], [1,2,0,3,4,5]]
        >>> a = [Permutation(p) for p in a]
        >>> g = Permutation([1,2,3,4,5,0])
        >>> G1,G2,G3 = [PermutationGroup(x) for x in [a[:2],a[2:4],[g,g**2]]]
        >>> assert G1.order() == G2.order() == G3.order() == 6
        >>> assert G1 == G2 and G1 != G3

        """
        if self.degree != gr.degree:
            return False
        if self.order() != gr.order():
            return False
        gens1 = self.generators
        for g in gens1:
            if not gr.has_element(g):
                return False
        return True

    def is_subgroup(self, gr):
        """
        test if self is a subgroup of gr

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1,2,3,4,0])
        >>> b = Permutation([1,0,2,3,4])
        >>> G = PermutationGroup([a, b])
        >>> c = Permutation([1,0,3,2,4])
        >>> G1 = PermutationGroup([a, c])
        >>> G1.is_subgroup(G)
        True

        """
        if self.degree != gr.degree:
            return False
        if self.order() > gr.order():
            return False
        gens1 = self.generators
        for g in gens1:
            if not gr.has_element(g):
                return False
        return True


    def __ne__(self, gr):
        return not self == gr

    def commutator(self):
        """
        commutator subgroup

        The commutator subgroup is the subgroup generated by all
        commutators; it is equal to the normal closure of the set
        of commutators of the generators.

        see http://groupprops.subwiki.org/wiki/Derived_subgroup

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1, 0, 2, 4, 3])
        >>> b = Permutation([0, 1, 3, 2, 4])
        >>> G = PermutationGroup([a, b])
        >>> C = G.commutator()
        >>> list(C.generate(af=True))
        [[0, 1, 2, 3, 4], [0, 1, 3, 4, 2], [0, 1, 4, 2, 3]]

        """
        r = self._r
        gens = [p.array_form for p in self.generators]
        gens_inv = [perm_af_invert(p) for p in gens]
        set_commutators = set()
        for i in range(r):
            for j in range(r):
                p1 = gens[i]
                p1inv = gens_inv[i]
                p2 = gens[j]
                p2inv = gens_inv[j]
                c = [p1[p2[p1inv[k]]] for k in p2inv]
                ct = tuple(c)
                if not ct in set_commutators:
                    set_commutators.add(ct)
        cms = [Permutation(p) for p in set_commutators]
        G2 = self.normal_closure(cms)
        return G2

    def is_solvable(self):
        """
        test if the group G is solvable

        G is solvable if the derived series
        G = G_0 < G_1 < ... < G_k = 1, with G_{i+1} = G.commutator()
        see http://en.wikipedia.org/wiki/Solvable_group

        Examples
        ========

        >>> from sympy.combinatorics.permutations import Permutation
        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> a = Permutation([1,2,0])
        >>> b = Permutation([1,0,2])
        >>> G = PermutationGroup([a, b])
        >>> G.is_solvable()
        True

        """
        order = self.order()
        if order == 1:
            return True
        G = self
        while order > 1:

            G = G.commutator()
            order1 = G.order()
            if order1 == order:
                return False
            order = order1
        return True

    def _random_pr_init(self, r, n, _random_prec_n=None):
        r"""
        Initializes random generators for the product replacement algorithm.

        The implementation uses a modification of the original product
        replacement algorithm due to Leedham-Green, as described in [1],
        pp.69-71; also, see [2], pp.27-29 for a detailed theoretical
        analysis of the original product replacement algorithm, and [4].

        The product replacement algorithm is used for producing random,
        uniformly distributed elements of a group `G` with a set of generators
        `S`. For the initialization ``_random_pr_init``, a list `R` of
        `\max\{r, |S|\}` group generators is created as the attribute
        ``G._random_gens``, repeating elements of `S` if necessary, and the
        identity element of `G` is appended to `R` - we shall refer to this
        last element as the accumulator. Then the function ``random_pr()``
        is called ``n`` times, randomizing the list `R` while preserving
        the generation of `G` by `R`. The function ``random_pr()`` itself
        takes two random elements `g, h` among all elements of `R` but
        the accumulator and replaces `g` with a randomly chosen element
        from `\{gh, g(~h), hg, (~h)g\}`. Then the accumulator is multiplied
        by whatever `g` was replaced by. The new value of the accumulator is
        then returned by ``random_pr()``.

        The elements returned will eventually (for ``n`` large enough) become
        uniformly distributed across `G` ([5]). For practical purposes however,
        the values ``n = 50, r = 11`` are suggested in [1].

        Notes
        =====

        THIS FUNCTION HAS SIDE EFFECTS: it changes the attribute
        self._random_gens

        See Also
        ========

        random_pr

        """
        deg = self.degree
        random_gens = self.generators[:]
        k = len(random_gens)
        if k < r:
            for i in range(k, r):
                random_gens.append(random_gens[i - k])
        acc = _new_from_array_form(range(deg))
        random_gens.append(acc)
        self._random_gens = random_gens

        # handle randomized input for testing purposes
        if _random_prec_n == None:
            for i in range(n):
                self.random_pr()
        else:
            for i in range(n):
                self.random_pr(_random_prec = _random_prec_n[i])

    def random_pr(self, gen_count=11, iterations=50, _random_prec=None):
        """
        Return a random group element using product replacement.

        For the details of the product replacement algorithm, see
        ``_random_pr_init`` In ``random_pr`` the actual 'product replacement'
        is performed. Notice that if the attribute ``_random_gens``
        is empty, it needs to be initialized by ``_random_pr_init``.

        See Also
        ========

        _random_pr_init

        """
        if self._random_gens == []:
            self._random_pr_init(gen_count, iterations)
        random_gens = self._random_gens
        r = len(random_gens) - 1

        # handle randomized input for testing purposes
        if _random_prec == None:
            s = randrange(r)
            t = randrange(r - 1)
            if t == s:
                t = r - 1
            x = choice([1, 2])
            e = choice([-1, 1])
        else:
            s = _random_prec['s']
            t = _random_prec['t']
            if t == s:
                t = r - 1
            x = _random_prec['x']
            e = _random_prec['e']

        if x == 1:
            random_gens[s] = random_gens[s]*(random_gens[t]**e)
            random_gens[r] = random_gens[r]*random_gens[s]
        else:
            random_gens[s] = (random_gens[t]**e)*random_gens[s]
            random_gens[r] = random_gens[s]*random_gens[r]
        return random_gens[r]

    def is_alt_sym(self, eps=0.05, _random_prec=None):
        r"""
        Monte Carlo test for the symmetric/alternating group for degrees >= 8.

        More specifically, it is one-sided Monte Carlo with the
        answer True (i.e., G is symmetric/alternating) guaranteed to be correct,
        and the answer False being incorrect with probability eps.

        Notes
        =====

        The algorithm itself uses some nontrivial results from group theory and
        number theory:
        1) If a transitive group `G` of degree ``n`` contains an element
        with a cycle of length `n/2 < p < n-2` for `p` a prime, `G` is the
        symmetric or alternating group ([1], pp.81-82)
        2) The proportion of elements in the symmetric/alternating group having
        the property described in 1) is approximately `\log(2)/\log(n)`
        ([1], p.82; [2], pp.226-227).
        The helper function ``_check_cycles_alt_sym`` is used to
        go over the cycles in a permutation and look for ones satisfying 1).

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> D = DihedralGroup(10)
        >>> D.is_alt_sym()
        False

        See Also
        ========

        _check_cycles_alt_sym

        """
        if _random_prec == None:
            n = self.degree
            if n < 8:
                return False
            if not self.is_transitive:
                return False
            if n < 17:
                c_n = 0.34
            else:
                c_n = 0.57
            d_n = (c_n*log(2))/log(n)
            N_eps = int(-log(eps)/d_n)
            for i in range(N_eps):
                perm = self.random_pr()
                if _check_cycles_alt_sym(perm):
                    return True
            return False
        else:
            for i in range(_random_prec['N_eps']):
                perm = _random_prec[i]
                if _check_cycles_alt_sym(perm):
                    return True
            return False

    def minimal_block(self, points):
        r"""
        For a transitive group, finds the block system generated by ``points``.

        If a group `G` acts on a set `S`, a nonempty subset `B` of `S` is
        called a block under the action of `G` if for all `g` in `G` we have
        `gB = B` (`g` fixes `B`) or `gB` and `B` have no common points
        (`g` moves `B` entirely). ([1], p.23; [6]).
        The distinct translates `gB` of a block `B` for `g` in `G` partition
        the set `S` and this set of translates is known as a block system.
        Moreover, we obviously have that all blocks in the partition have
        the same size, hence the block size divides `|S|` ([1], p.23).
        A `G`-congruence is an equivalence relation `~` on the set `S` such that
        `a ~ b` implies `g(a) ~ g(b)` for all `g` in `G`. For a
        transitive group, the equivalence classes of a `G`-congruence and the
        blocks of a block system are the same thing ([1], p.23).
        The algorithm below checks the group for transitivity, and then finds
        the `G`-congruence generated by the pairs `(p_0, p_1), (p_0, p_2), ...,
        (p_0,p_{k-1})` which is the same as finding the maximal block system
        (i.e., the one with minimum block size) such that
        `p_0, ..., p_{k-1}` are in the same block ([1], p.83).
        It is an implementation of Atkinson's algorithm, as suggested in [1],
        and manipulates an equivalence relation on the set `S` using a
        union-find data structure. The running time is just above
        `O(|points||S|)`. ([1], pp.83-87; [7]).

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> D = DihedralGroup(10)
        >>> D.minimal_block([0,5])
        [0, 6, 2, 8, 4, 0, 6, 2, 8, 4]
        >>> D.minimal_block([0,1])
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        See Also
        ========

        _union_find_rep, _union_find_merge, is_transitive, is_primitive

        """
        if not self.is_transitive:
            return False
        n = self.degree
        gens = self.generators
        # initialize the list of equivalence class representatives
        parents = range(n)
        ranks = [1]*n
        not_rep = []
        k = len(points)
        # the block size must divide the degree of the group
        if k > self.max_div:
            return [0]*n
        for i in xrange(k-1):
            parents[points[i+1]] = points[0]
            not_rep.append(points[i+1])
        ranks[points[0]] = k
        i = 0
        len_not_rep = k-1
        while i < len_not_rep:
            temp = not_rep[i]
            i += 1
            for gen in gens:
                # find has side effects: performs path compression on the list
                # of representatives
                delta = self._union_find_rep(temp, parents)
                # union has side effects: performs union by rank on the list
                # of representatives
                temp = self._union_find_merge(gen(temp), gen(delta), ranks,\
                                                 parents, not_rep)
                if temp == -1:
                    return [0]*n
                len_not_rep += temp
        for i in range(n):
            # force path compression to get the final state of the equivalence
            # relation
            self._union_find_rep(i, parents)
        return parents

    def _union_find_rep(self, num, parents):
        """
        Find representative of a class in a union-find data structure.

        Used in the implementation of Atkinson's algorithm as suggested in [1],
        pp.83-87. After the representative of the class to which ``num``
        belongs is found, path compression is performed as an optimization
        ([7]).

        Notes
        =====

        THIS FUNCTION HAS SIDE EFFECTS: the list of class representatives,
        ``parents``, is altered due to path compression.

        See Also
        ========

        minimal_block, _union_find_merge

        References
        ==========

        [1] Holt, D., Eick, B., O'Brien, E.
        "Handbook of computational group theory"

        [7] http://www.algorithmist.com/index.php/Union_Find

        """
        rep, parent = num, parents[num]
        while parent != rep:
            rep = parent
            parent = parents[rep]
        # path compression
        temp, parent = num, parents[num]
        while parent != rep:
            parents[temp] = rep
            temp = parent
            parent = parents[temp]
        return rep

    def _union_find_merge(self, first, second, ranks, parents, not_rep):
        """
        Merges two classes in a union-find data structure.

        Used in the implementation of Atkinson's algorithm as suggested in [1],
        pp.83-87. The class merging process uses union by rank as an
        optimization. ([7])

        Notes
        =====

        THIS FUNCTION HAS SIDE EFFECTS: the list of class representatives,
        ``parents``, the list of class sizes, ``ranks``, and the list of
        elements that are not representatives, ``not_rep``, are changed due to
        class merging.

        See Also
        ========

        minimal_block, _union_find_rep

        References
        ==========

        [1] Holt, D., Eick, B., O'Brien, E.
        "Handbook of computational group theory"

        [7] http://www.algorithmist.com/index.php/Union_Find

        """
        rep_first = self._union_find_rep(first, parents)
        rep_second = self._union_find_rep(second, parents)
        if rep_first != rep_second:
            # union by rank
            if ranks[rep_first] >= ranks[rep_second]:
                new_1, new_2 = rep_first, rep_second
            else:
                new_1, new_2 = rep_second, rep_first
            total_rank = ranks[new_1] + ranks[new_2]
            if total_rank > self.max_div:
                return -1
            parents[new_2] = new_1
            ranks[new_1] = total_rank
            not_rep.append(new_2)
            return 1
        return 0

    @property
    def max_div(self):
        """
        Maximum proper divisor of the degree of a permutation group.

        Notes
        =====

        Obviously, this is the degree divided by its minimal proper divisor
        (larger than `1`, if one exists). As it is guaranteed to be prime,
        the ``sieve`` from ``sympy.ntheory`` is used.
        This function is also used as an optimization tool for the functions
        ``minimal_block`` and ``_union_find_merge``.

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.permutations import Permutation
        >>> G = PermutationGroup([Permutation([0,2,1,3])])
        >>> G.max_div
        2

        See Also
        ========

        minimal_block, _union_find_merge

        """
        if self._max_div != None:
            return self._max_div
        n = self.degree
        if n == 1:
            return 1
        for x in sieve:
            if n % x == 0:
                d = n//x
                self._max_div = d
                return d


    def is_primitive(self, randomized=True):
        """
        Test a group for primitivity.

        A permutation group `G` acting on a set `S` is called primitive if
        `S` contains no nontrivial block under the action of `G`
        (a block is nontrivial if its cardinality is more than `1`).

        Notes
        =====

        The algorithm is described in [1], p.83, and uses the function
        minimal_block to search for blocks of the form `\{0, k\}` for `k`
        ranging over representatives for the orbits of `G_0`, the stabilizer of
        `0`. This algorithm has complexity `O(n^2)` where `n` is the degree
        of the group, and will perform badly if `G_0` is small.

        There are two implementations offered: one finds `G_0`
        deterministically using the function ``stabilizer``, and the other
        (default) produces random elements of `G_0` using ``random_stab``,
        hoping that they generate a subgroup of `G_0` with not too many more
        orbits than G_0 (this is suggested in [1], p.83). Behavior is changed
        by the ``randomized`` flag.

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.named_groups import DihedralGroup
        >>> D = DihedralGroup(10)
        >>> D.is_primitive()
        False

        See Also
        ========

        minimal_block, random_stab

        """
        if self._is_primitive != None:
            return self._is_primitive
        n = self.degree
        if randomized:
            r = len(self.generators)
            random_stab_gens = []
            v = self.schreier_vector(0)
            for i in range(r):
                random_stab_gens.append(self.random_stab(0, v))
            stab = PermutationGroup(random_stab_gens)
        else:
            stab = self.stabilizer(0)
        orbits = stab.orbits()
        for orb in orbits:
            x = orb.pop()
            if x != 0 and self.minimal_block([0, x]) != [0]*n:
                self._is_primitive = False
                return False
        self._is_primitive = True
        return True

    def random_stab(self, alpha, schreier_vector=None, _random_prec=None):
        """
        Random element from the stabilizer of ``alpha``.

        The schreier vector for ``alpha`` is an optional argument used
        for speeding up repeated calls. The algorithm is described in [1], p.81

        See Also
        ========

        random_pr, orbit_rep

        """
        if schreier_vector == None:
            schreier_vector = self.schreier_vector(alpha)
        if _random_prec == None:
            rand = self.random_pr()
        else:
            rand = _random_prec['rand']
        beta = rand(alpha)
        h = self.orbit_rep(alpha, beta, schreier_vector)
        return (~h)*rand

    @property
    def transitivity_degree(self):
        """
        Compute the degree of transitivity of the group.

        A permutation group `G` acting on `\Omega = \{0, 2, ..., n-1\}` is
        `k`-fold transitive, if, for any k points
        `(a_1, a_2, ..., a_k)\in\Omega` and any k points
        `(b_1, b_2, ..., b_k)\in\Omega` there exists `g\in G` such that
        `g(a_1)=b_1, g(a_2)=b_2, ..., g(a_k)=b_k`
        The degree of transitivity of `G` is the maximum `k` such that
        `G` is `k`-fold transitive. ([8])

        Examples
        ========

        >>> from sympy.combinatorics.perm_groups import PermutationGroup
        >>> from sympy.combinatorics.permutations import Permutation
        >>> a = Permutation([1, 2, 0])
        >>> b = Permutation([1, 0, 2])
        >>> G = PermutationGroup([a,b])
        >>> G.transitivity_degree
        3

        See Also
        ========
        is_transitive, orbit

        """
        if self._transitivity_degree is None:
            n = self.degree
            max_size = 1
            for i in range(1, n + 1):
                max_size *= n - i + 1
                orb = self.orbit(range(i), 'tuples')
                if len(orb) != max_size:
                    return i - 1
            self._transitivity_degree = n
            return n
        else:
            return self._transitivity_degree

    def schreier_sims_random(self, base=None, gens=None, consec_succ=10,\
                             _random_prec=None):
        r"""
        Randomized Schreier-Sims algorithm.

        The randomized Schreier-Sims algorithm takes the sequence ``base``
        and the generating set ``gens``, and extends ``base`` to a base, and
        ``gens`` to a strong generating set relative to that base with
        probability of a wrong answer at most `1/\text{consec_succ}`.

        Notes
        =====

        The algorithm is described in detail in [1],pp.97-98. It extends
        the orbits ``orbs`` and the permutation groups ``stabs`` to
        basic orbits and basic stabilizers for the base and strong generating
        set produced in the end.
        The idea of the extension process
        is to "sift" random group elements through the stabilizer chain
        and amend the stabilizers/orbits along the way when a sift
        is not successful.
        The helper function ``_strip`` is used to attempt
        to decompose a random group element according to the current
        state of the stabilizer chain and report whether the element was
        fully decomposed (successful sift) or not (unsuccessful sift). In
        the latter case, the level at which the sift failed is reported and
        used to amend ``stabs``, ``base``, ``gens`` and ``orbs`` accordingly.
        The halting condition is for ``consec_succ`` consecutive successful
        sifts to pass. This makes sure that the current ``base`` and ``gens``
        form a BSGS with probability at least `1 - 1/\text{consec_succ}`.

        See Also
        ========

        schreier_sims

        """
        if base is None:
            base = []
        if gens is None:
            gens = self.generators
        base_len = len(base)
        n = self.degree
        # make sure no generator fixes all base points
        for gen in gens:
            if [gen(x) for x in base] == [x for x in base]:
                new = 0
                while gen(new) == new:
                    new += 1
                base.append(new)
                base_len += 1
        # distribute generators according to basic stabilizers
        distr_gens = _distribute_gens_by_base(base, gens)
        # initialize the basic stabilizers, basic transversals and basic orbits
        stabs = {}
        transversals = {}
        orbs = {}
        for i in xrange(base_len):
            stabs[i] = PermutationGroup(distr_gens[i])
            transversals[i] = dict(stabs[i].orbit_transversal(base[i],\
                                                              pairs=True))
            orbs[i] = transversals[i].keys()
        # initialize the number of consecutive elements sifted
        c = 0
        # start sifting random elements while the number of consecutive sifts
        # is less than consec_succ
        while c < consec_succ:
            if _random_prec is None:
                g = self.random_pr()
            else:
                g = _random_prec['g'].pop()
            h, j = _strip(g, base, orbs, transversals)
            y = True
            # determine whether a new base point is needed
            if j <= base_len:
                y = False
            elif not h.is_Identity:
                y = False
                moved = 0
                while h(moved) == moved:
                    moved += 1
                base.append(moved)
                base_len += 1
                distr_gens.append([])
            # if the element doesn't sift, amend the strong generators and
            # associated stabilizers and orbits
            if y == False:
                for l in range(1, j):
                    distr_gens[l].append(h)
                    stabs[l] = PermutationGroup(distr_gens[l])
                    transversals[l] = dict(stabs[l].orbit_transversal(base[l],\
                                                                    pairs=True))
                    orbs[l] = transversals[l].keys()
                c = 0
            else:
                c += 1
        # build the strong generating set
        strong_gens = distr_gens[0][:]
        for gen in distr_gens[1]:
            if gen not in strong_gens:
                strong_gens.append(gen)
        return base, strong_gens

    def list_lex_by_base(self, base, strong_gens, transversals=None,\
                         basic_orbits=None, distr_gens=None):
        """
        List all group elements in increasing order of base images.

        For a group `G` with a base `(b_1, b_2, ..., b_k)`, the element `g`
        precedes the element `h` in the order of base images if
        `(g(b_1), g(b_2), ..., g(b_k))` precedes
        `(h(b_1), h(b_2), ..., h(b_k))` in the lexicographical ordering of
        `\{0, 1, ..., n-1\}` induced by the base (i.e., base points come first
        and in order, and non-base points come after that and in the usual
        ordering).

        Parameters
        ==========

        ``base``, ``strong_gens`` - the base and strong generating set
        ``transversals`` - transversals for the basic orbits, if known
        ``basic_orbits`` - basic orbits, if known
        ``distr_gens`` - strong generators distributed by basic stabilizers,
        if known

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import SymmetricGroup
        >>> S = SymmetricGroup(3)
        >>> S.schreier_sims()
        >>> S.list_lex_by_base(S.base, S.strong_gens)
        [Permutation([0, 1, 2]), Permutation([0, 2, 1]),\
        Permutation([1, 0, 2]), Permutation([1, 2, 0]),\
        Permutation([2, 0, 1]), Permutation([2, 1, 0])]

        >>> S.base
        [0, 1]

        Notes
        =====

        This is a depth-first search visiting all group elements. Printing is
        done once the current group elements is fully constructed from the
        transversal elements found from the base and strong generating sets.
        This basic way of traversing the group is used in backtracking
        algorithms in order to "prune" the search tree by testing partial
        base images for certain properties and thus avoid visiting large
        numbers of group elements. The algorithm and possible implementations
        are discussed in [1],pp.110-111. For a group `G` with a base
        `(b_1, b_2, ..., b_k)`, the current solution for storing the
        partial decomposition `u_1u_2...u_l` for `l < k` of a group element
        `g = u_1u_2...u_k` is to keep an array the `l`-th entry of which
        is `u_1u_2...u_l` and update it accordingly.

        See Also
        ========

        _base_ordering from sympy.combinatorics.util

        """
        result = []
        degree = self.degree
        # order the points in range(degree) according to the base
        base_ordering = _base_ordering(base, degree)
        # construct the basic orbits, generators for the stabilizer chain
        # and transversal elements from whatever was provided
        transversals, basic_orbits, distr_gens =\
        _handle_precomputed_bsgs(base, strong_gens, transversals,\
                                 basic_orbits, distr_gens)
        # initialize sorted orbits
        base_len = len(base)
        c = [0]*base_len
        u = [None]*base_len
        sorted_orbits = [None]*base_len
        u[0] = _new_from_array_form(range(degree))
        # sort the first basic orbit according to the base ordering
        sorted_orbits[0] = basic_orbits[0][:]
        sorted_orbits[0].sort(key = lambda point: base_ordering[point])
        # set the depth of the search
        depth = 0
        computed_words = [0]*base_len
        computed_words[0] = u[0]
        # depth-first search
        while True:
            # in this loop, initialize the new branches of the search tree
            while depth < base_len - 1:
                depth += 1
                g = computed_words[depth - 1]
                orb_image = [g(point) for point in basic_orbits[depth]]
                # order the orbit image according to the base ordering
                orb_image.sort(key = lambda point: base_ordering[point])
                sorted_orbits[depth] = orb_image
                # now set the transversal element so that the image of
                # base[depth] under u[0]*...*u[l] is smallest in the base
                # ordering
                c[depth] = 0
                g_inverse = ~g
                gamma = g_inverse(sorted_orbits[depth][c[depth]])
                u[depth] = transversals[depth][gamma]
                computed_words[depth] = computed_words[depth - 1]*u[depth]
            # append whatever we have at depth = base_len-1 to the result
            output = computed_words[base_len - 1]
            result.append(output)
            # go up the tree to the first branch that is not searched entirely
            while depth >= 0 and c[depth] + 1 == len(basic_orbits[depth]):
                depth -= 1
            if depth == -1:
                return result
            # find the next element in the ordering
            c[depth] += 1
            if depth == 0:
                g = _new_from_array_form(range(degree))
            else:
                g = computed_words[depth - 1]
            g_inverse = ~g
            gamma = g_inverse(sorted_orbits[depth][c[depth]])
            u[depth] = transversals[depth][gamma]
            if depth == 0:
                computed_words[depth] = u[depth]
            else:
                computed_words[depth] = computed_words[depth - 1]*u[depth]

    def baseswap(self, base, strong_gens, pos, randomized=True,\
                 transversals=None, basic_orbits=None, distr_gens=None):
        r"""
        Swap two consecutive base points in a base and strong generating set.

        If a base for a group `G` is given by `(b_1, b_2, ..., b_k)`, this
        function returns a base `(b_1, b_2, ..., b_{i+1}, b_i, ..., b_k)`,
        where `i` is given by ``pos``, and a strong generating set relative
        to that base. The original base and strong generating set are not
        modified.
        The randomized version (default) is of Las Vegas type.

        Parameters
        ==========

        ``base``, ``strong_gens`` - the base and strong generating set
        ``pos`` - position at which swapping is performed
        ``randomized`` - switch between randomized and deterministic version
        ``transversals`` - transversals for the basic orbits, if known
        ``basic_orbits`` - basic orbits, if known
        ``distr_gens`` - strong generators distributed by basic stabilizers,
        if known

        Examples
        ========

        >>> from sympy.combinatorics.named_groups import SymmetricGroup
        >>> S = SymmetricGroup(4)
        >>> S.schreier_sims()
        >>> S.baseswap(S.base, S.strong_gens, 1, randomized=False)
        ([0, 2, 1], [Permutation([1, 2, 3, 0]), Permutation([1, 0, 2, 3]), Permutation([0, 1, 3, 2]), Permutation([0, 3, 1, 2]), Permutation([0, 3, 2, 1])])
        >>> S.base
        [0, 1, 2]

        See Also
        ========

        schreier_sims

        Notes
        =====

        The deterministic version of the algorithm is discussed in
        [1],pp.102-103; the randomized version is discussed in [1],p.103, and
        [2],p.98. It is of Las Vegas type.
        Notice that [1] contains a mistake in the pseudocode and
        discussion of BASESWAP: on line 3 of the pseudocode,
        `|\beta_{i+1}^\left\langle T\right\rangle|` should be replaced by
        `|\beta_{i}^\left\langle T\right\rangle|`, and the same for the
        discussion of the algorithm.

        """
        # construct the basic orbits, generators for the stabilizer chain
        # and transversal elements from whatever was provided
        transversals, basic_orbits, distr_gens =\
        _handle_precomputed_bsgs(base, strong_gens, transversals,\
                                 basic_orbits, distr_gens)
        base_len = len(base)
        degree = self.degree
        stab_pos = PermutationGroup(distr_gens[pos])
        # size of orbit of base[pos] under the stabilizer we seek to insert
        # in the stabilizer chain at position pos + 1
        size = len(basic_orbits[pos])*len(basic_orbits[pos + 1])\
               //len(stab_pos.orbit(base[pos + 1]))
        # initialize the wanted stabilizer by a subgroup
        if pos + 2 > base_len - 1:
            T = []
        else:
            T = distr_gens[pos + 2][:]
        if T == []:
            current_group = PermGroup([_new_from_array_form(range(degree))])
        else:
            current_group = PermGroup(T)
        # randomized version
        if randomized is True:
            schreier_vector = stab_pos.schreier_vector(base[pos + 1])
            # add random elements of the stabilizer until they generate it
            while len(current_group.orbit(base[pos])) != size:
                new = stab_pos.random_stab(base[pos + 1],\
                                           schreier_vector=schreier_vector)
                T.append(new)
                current_group = PermutationGroup(T)
        # deterministic version
        else:
            Gamma = set(basic_orbits[pos])
            Gamma.remove(base[pos])
            if base[pos + 1] in Gamma:
                Gamma.remove(base[pos + 1])
            # add elements of the stabilizer until they generate it by
            # ruling out member of the basic orbit of base[pos] along the way
            while len(current_group.orbit(base[pos])) != size:
                gamma = iter(Gamma).next()
                x = transversals[pos][gamma]
                x_inverse = ~x
                temp = x_inverse(base[pos + 1])
                if temp not in basic_orbits[pos + 1]:
                    Gamma = Gamma - current_group.orbit(gamma)
                else:
                    y = transversals[pos + 1][temp]
                    el = x*y
                    if el(base[pos]) not in current_group.orbit(base[pos]):
                        T.append(el)
                        current_group = PermutationGroup(T)
                        Gamma = Gamma - current_group.orbit(base[pos])
        # build the new base and strong generating set
        strong_gens_new_distr = distr_gens[:]
        strong_gens_new_distr[pos + 1] = T
        base_new = base[:]
        base_new[pos], base_new[pos + 1] = base_new[pos + 1], base_new[pos]
        strong_gens_new = _strong_gens_from_distr(strong_gens_new_distr)
        for gen in T:
            if gen not in strong_gens_new:
                strong_gens_new.append(gen)
        return base_new, strong_gens_new

    def schreier_sims_incremental(self, base=None, gens=None):
        if base is None:
            base = []
        if gens is None:
            gens = self.generators
        base_len = len(base)
        degree = self.degree
        # handle the trivial group
        if gens == [_new_from_array_form(range(degree))]:
            return base, gens
        # make sure no generator fixes all base points
        for gen in gens:
            if gen != _new_from_array_form(range(degree)) and [gen(x) for x in base] == [x for x in base]:
                new = 0
                while gen(new) == new:
                    new += 1
                base.append(new)
                base_len += 1
        # distribute generators according to basic stabilizers
        distr_gens = _distribute_gens_by_base(base, gens)
        # initialize the basic stabilizers, basic orbits and basic transversals
        stabs = {}
        orbs = {}
        transversals = {}
        for i in xrange(base_len):
            stabs[i] = PermutationGroup(distr_gens[i])
            transversals[i] = dict(stabs[i].orbit_transversal(base[i],\
                                                              pairs=True))
            orbs[i] = transversals[i].keys()
        i = base_len - 1
        while i >= 0:
            continue_i = False
            for beta in orbs[i]:
                u_beta = transversals[i][beta]
                for gen in distr_gens[i]:
                    u_beta_gen = transversals[i][gen(beta)]
                    if gen*u_beta != u_beta_gen:
                        y = True
                        schreier_gen = (~u_beta_gen)*gen*u_beta
                        h, j = _strip(schreier_gen, base, orbs, transversals)
                        if j <= base_len:
                            y = False
                        elif h != _new_from_array_form(range(degree)):
                            y = False
                            moved = 0
                            while h(moved) == moved:
                                moved += 1
                            base.append(moved)
                            base_len += 1
                            distr_gens.append([])
                        if y == False:
                            for l in range(i + 1, j):
                                distr_gens[l].append(h)
                                stabs[l] = PermutationGroup(distr_gens[l])
                                transversals[l] =\
                                dict(stabs[l].orbit_transversal(base[l],\
                                                                pairs=True))
                                orbs[l] = transversals[l].keys()
                            i = j - 1
                            continue_i = True
                    if continue_i == True:
                        break
                if continue_i == True:
                    break
            if continue_i == True:
                continue
            i -= 1
        strong_gens = []
        for gens in distr_gens:
            for gen in gens:
                if gen not in strong_gens:
                    strong_gens.append(gen)
        return base, strong_gens

    def subgroup_search(self, prop, base=None, strong_gens=None, tests=None, init_subgroup=None):
        # initialize BSGS and basic group properties
        if base is None:
            base, strong_gens = self.schreier_sims_incremental()
        base_len = len(base)
        degree = self.degree
        identity = _new_from_array_form(range(degree))
        base_ordering = _base_ordering(base, degree)
        # add an element larger than all points
        base_ordering.append(degree)
        # add an element smaller than all points
        base_ordering.append(-1)
        # compute BSGS-related structures
        distr_gens = _distribute_gens_by_base(base, strong_gens)
        basic_orbits, transversals = _orbits_transversals_from_bsgs(base, distr_gens)
        # handle subgroup initialization and tests
        if init_subgroup is None:
            init_subgroup = PermutationGroup([identity])
        if tests is None:
            trivial_test = lambda x: True
            tests = []
            for i in xrange(base_len):
                tests.append(trivial_test)
        # line 1: more initializations.
        res = init_subgroup
        f = base_len - 1
        l = base_len - 1
        # line 2: set the base for K to the base for G
        res_base = base[:]
        # line 3: compute BSGS and related structures for K
        res_base, res_strong_gens = res.schreier_sims_incremental(base=res_base)
        res_distr_gens = _distribute_gens_by_base(res_base, res_strong_gens)
        res_basic_orbits, res_transversals = _orbits_transversals_from_bsgs(res_base, res_distr_gens)
        res_basic_orbits_init_base = res_basic_orbits[:]
        res_strong_gens_init = res_strong_gens[:]
        # initialize orbit representatives
        orbit_reps = [None]*base_len
        # line 4: orbit representatives for f-th basic stabilizer of K
        stab_f = PermutationGroup(res_distr_gens[f])
        orbits = stab_f.orbits()
        reps = []
        for orbit in orbits:
            # get the minimal element in the base ordering
            rep = min(orbit, key = lambda point: base_ordering[point])
            reps.append(rep)
        orbit_reps[f] = reps
        # line 5: remove the base point from the representatives to avoid
        # getting the identity element as a generator for K
        orbit_reps[f].remove(base[f])
        # line 6: more initializations
        c = [0]*base_len
        u = [identity]*base_len
        sorted_orbits = [None]*base_len
        for i in range(base_len):
            sorted_orbits[i] = basic_orbits[i][:]
            sorted_orbits[i].sort(key = lambda point: base_ordering[point])
        # line 7: initializations
        mu = [None]*base_len
        nu = [None]*base_len
        # this corresponds to the element smaller than all points
        mu[l] = degree + 1
        temp_index = len(basic_orbits[l])+1-len(res_basic_orbits_init_base[l])
        if temp_index >= len(basic_orbits[l]):
            # this corresponds to the element larger than all points
            nu[l] = base_ordering[degree]
        else:
            nu[l] = sorted_orbits[l][temp_index]
        # initialize computed words
        computed_words = [identity]*base_len
        # line 8: main loop
        while True:
            # apply all the tests
            while l < base_len - 1 and\
                  computed_words[l](base[l]) in orbit_reps[l] and\
                  base_ordering[computed_words[l](base[l])] > base_ordering[mu[l]] and\
                  base_ordering[computed_words[l](base[l])] < base_ordering[nu[l]] and\
                  tests[l](computed_words[base_len - 1]):
                # line 11: change the (partial) base of K
                new_point = computed_words[l](base[l])
                # this function maintains a partial BSGS structure up to position l
                _insert_point_in_base(res, res_base, res_strong_gens, l, new_point, distr_gens=res_distr_gens, basic_orbits=res_basic_orbits, transversals=res_transversals)
                # find the l+1-th basic stabilizer
                new_stab = PermutationGroup(res_distr_gens[l + 1])
                # line 12: calculate minimal orbit representatives for the l+1-th basic stabilizer
                orbits = new_stab.orbits()
                reps = []
                for orbit in orbits:
                    rep = min(orbit, key = lambda point: base_ordering[point])
                    reps.append(rep)
                orbit_reps[l + 1] = reps
                # line 13: amend sorted orbits
                l += 1
                temp_orbit = [computed_words[l-1](point) for point in basic_orbits[l]]
                temp_orbit.sort(key = lambda point: base_ordering[point])
                sorted_orbits[l] = temp_orbit
                # lines 14 and 15: update variables used minimality tests
                new_mu = degree + 1
                for i in range(l):
                    if base[l] in res_basic_orbits_init_base[i]:
                        candidate = computed_words[i](base[i])
                        if base_ordering[candidate] > base_ordering[new_mu]:
                            new_mu = candidate
                mu[l] = new_mu
                temp_index = len(basic_orbits[l]) + 1 - len(res_basic_orbits_init_base[l])
                if temp_index >= len(sorted_orbits[l]):
                    nu[l] = base_ordering[degree]
                else:
                    nu[l] = sorted_orbits[l][temp_index]
                # line 16: determine the new transversal element
                c[l] = 0
                temp_point = sorted_orbits[l][c[l]]
                temp_element = ~(computed_words[l - 1])
                gamma = temp_element(temp_point)
                u[l] = transversals[l][gamma]
                # update computed words
                computed_words[l] = computed_words[l-1] * u[l]
            # lines 17 & 18: apply the tests to the group element found
            g = computed_words[l]
            temp_point = g(base[l])
            if l == base_len - 1 and\
               base_ordering[temp_point] > base_ordering[mu[l]] and\
               base_ordering[temp_point] < base_ordering[nu[l]] and\
               temp_point in orbit_reps[l] and\
               tests[l](g) and\
               prop(g):
                # line 19: reset the base of K
                gens = res.generators[:]
                gens.append(g)
                res = PermutationGroup(gens)
                res_base = base[:]
                # line 20: recalculate basic orbits (and transversals)
                res_strong_gens_init.append(g)
                res_distr_gens = _distribute_gens_by_base(res_base, res_strong_gens_init)
                res_basic_orbits, res_transversals = _orbits_transversals_from_bsgs(res_base, res_distr_gens)
                res_basic_orbits_init_base = res_basic_orbits[:]
                res_strong_gens = res_strong_gens_init[:]
                # line 21: recalculate orbit representatives
                stab_f = PermutationGroup(res_distr_gens[f])
                temp_orbits = stab_f.orbits()
                reps = []
                for orbit in orbits:
                    rep = min(orbit, key = lambda point: base_ordering[point])
                    reps.append(rep)
                orbit_reps[f] = reps
                # line 22: reset the search depth
                l = f
            # line 23: go up the tree until in the first branch not fully searched
            while l >= 0 and c[l] == len(basic_orbits[l]) - 1:
                l = l - 1
            # line 24: if the entire tree is traversed, return K
            if l == -1:
                return res
            # lines 25
            if l < f:
                # line 26
                f = l
                c[l] = 0
                # line 27
                temp_orbits = stab_f.orbits()
                reps = []
                for orbit in orbits:
                    rep = min(orbit, key = lambda point: base_ordering[point])
                    reps.append(rep)
                orbit_reps[f] = reps
                # line 28
                mu[l] = degree + 1
                temp_index = len(basic_orbits[l]) + 1 - len(res_basic_orbits_init_base[l])
                if temp_index >= len(sorted_orbits[l]):
                    nu[l] = base_ordering[degree]
                else:
                    nu[l] = sorted_orbits[l][temp_index]
            # line 29
            c[l] += 1
            element = ~(computed_words[l - 1])
            gamma  = element(sorted_orbits[l][c[l]])
            u[l] = transversals[l][gamma]
            if l == 0:
                computed_words[l] = u[l]
            else:
                computed_words[l] = computed_words[l - 1]*u[l]

def DirectProduct(*groups):
    """
    Returns the direct product of several groups as a permutation group.

    This is implemented much like the __mul__ procedure for taking the direct
    product of two permutation groups, but the idea of shifting the
    generators is realized in the case of an arbitrary number of groups.
    A call to DirectProduct(G1, G2, ..., Gn) is generally expected to be faster
    than a call to G1*G2*...*Gn (and thus the need for this algorithm).

    Examples
    ========

    >>> from sympy.combinatorics.perm_groups import DirectProduct
    >>> from sympy.combinatorics.named_groups import CyclicGroup
    >>> C = CyclicGroup(4)
    >>> G = DirectProduct(C,C,C)
    >>> G.order()
    64

    See Also
    ========
    __mul__

    """
    degrees = []
    gens_count = []
    total_degree = 0
    total_gens = 0
    for group in groups:
        current_deg = group.degree
        current_num_gens = len(group.generators)
        degrees.append(current_deg)
        total_degree += current_deg
        gens_count.append(current_num_gens)
        total_gens += current_num_gens
    array_gens = []
    for i in range(total_gens):
        array_gens.append(range(total_degree))
    current_gen = 0
    current_deg = 0
    for i in xrange(len(gens_count)):
        for j in xrange(current_gen, current_gen + gens_count[i]):
            gen = ((groups[i].generators)[j - current_gen]).array_form
            array_gens[j][current_deg:current_deg + degrees[i]] =\
            [ x + current_deg for x in gen]
        current_gen += gens_count[i]
        current_deg += degrees[i]
    perm_gens = [_new_from_array_form(array) for array in array_gens]
    return PermutationGroup(perm_gens)

PermGroup = PermutationGroup
