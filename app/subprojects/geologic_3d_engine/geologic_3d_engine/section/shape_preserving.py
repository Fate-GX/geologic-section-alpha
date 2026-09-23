"""C1, interval-monotone cubic Hermite interpolation; no extrapolation."""
import numpy as np


def interpolate(x, y, query):
    x, y, q = map(lambda a: np.asarray(a, dtype=float), (x, y, query))
    if x.ndim != 1 or y.shape != x.shape or len(x) < 2 or not all(np.isfinite(a).all() for a in (x,y,q)):
        raise ValueError("finite one-dimensional samples required")
    h = np.diff(x)
    if np.any(h <= 0) or np.any(q < x[0]) or np.any(q > x[-1]):
        raise ValueError("ordered samples and in-domain queries required")
    delta = np.diff(y)/h
    d = np.zeros_like(y)
    if len(x) == 2:
        d[:] = delta[0]
    else:
        for i in range(1,len(x)-1):
            if delta[i-1]*delta[i] > 0:
                w1, w2 = 2*h[i]+h[i-1], h[i]+2*h[i-1]
                d[i] = (w1+w2)/(w1/delta[i-1]+w2/delta[i])
        for index,a,b,u,v in ((0,h[0],h[1],delta[0],delta[1]),(-1,h[-1],h[-2],delta[-1],delta[-2])):
            slope=((2*a+b)*u-a*v)/(a+b)
            if slope*u <= 0: slope=0
            elif u*v <= 0 and abs(slope)>3*abs(u): slope=3*u
            d[index]=slope
    i=np.clip(np.searchsorted(x,q,side="right")-1,0,len(x)-2)
    t=(q-x[i])/h[i]
    return (2*t**3-3*t**2+1)*y[i]+(t**3-2*t**2+t)*h[i]*d[i]+(-2*t**3+3*t**2)*y[i+1]+(t**3-t**2)*h[i]*d[i+1]
