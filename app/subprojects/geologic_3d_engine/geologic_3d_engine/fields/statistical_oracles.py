"""High-precision reference moments for statistical validation only."""

from __future__ import annotations
import math


def _adaptive_simpson(function, left, right, tolerance, maximum_depth=24):
    def simpson(a, b, fa, fm, fb): return (b-a)*(fa+4*fm+fb)/6
    fa=function(left);fb=function(right);middle=(left+right)/2;fm=function(middle)
    whole=simpson(left,right,fa,fm,fb)
    def recurse(a,b,fa,fm,fb,estimate,tol,depth):
        m=(a+b)/2;lm=(a+m)/2;rm=(m+b)/2;flm=function(lm);frm=function(rm)
        lower=simpson(a,m,fa,flm,fm);upper=simpson(m,b,fm,frm,fb);refined=lower+upper
        if depth<=0 or abs(refined-estimate)<=15*tol:return refined+(refined-estimate)/15
        return recurse(a,m,fa,flm,fm,lower,tol/2,depth-1)+recurse(m,b,fm,frm,fb,upper,tol/2,depth-1)
    return recurse(left,right,fa,fm,fb,whole,tolerance,maximum_depth)


def positive_part_normal_moment(*, variance: float, threshold: float, power: float,
                                absolute_tolerance: float = 1e-12,
                                upper_standard_deviations: float = 12.0) -> float:
    """Return E[max(X-threshold,0)^power], X~N(0,variance)."""
    if not all(math.isfinite(v) for v in (variance,threshold,power,absolute_tolerance,upper_standard_deviations)):
        raise ValueError("oracle parameters must be finite")
    if variance<=0 or power<=0 or absolute_tolerance<=0 or upper_standard_deviations<=0:
        raise ValueError("variance, power, tolerance and upper bound must be positive")
    sigma=math.sqrt(variance);upper=max(threshold,0.0)+upper_standard_deviations*sigma
    normalizer=1/(sigma*math.sqrt(2*math.pi))
    def integrand(x):return ((x-threshold)**power)*normalizer*math.exp(-(x*x)/(2*variance))
    return _adaptive_simpson(integrand,threshold,upper,absolute_tolerance)
