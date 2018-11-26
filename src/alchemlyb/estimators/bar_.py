import numpy as np
import pandas as pd

from sklearn.base import BaseEstimator

from pymbar import BAR as BAR_


class BAR(BaseEstimator):
    """Bennett acceptance ratio (BAR).

    Parameters
    ----------

    maximum_iterations : int, optional
        Set to limit the maximum number of iterations performed.

    relative_tolerance : float, optional
        Set to determine the relative tolerance convergence criteria.

    method : str, optional, defualt='false-position'
        choice of method to solve BAR nonlinear equations,
        one of 'self-consistent-iteration' or 'false-position' (default: 'false-position')

    verbose : bool, optional
        Set to True if verbose debug output is desired.

    Attributes
    ----------

    delta_f_ : DataFrame
        The estimated dimensionless free energy difference between each state.

    d_delta_f_ : DataFrame
        The estimated statistical uncertainty (one standard deviation) in
        dimensionless free energy differences.

    states_ : list
        Lambda states for which free energy differences were obtained.

    """

    def __init__(self, maximum_iterations=10000, relative_tolerance=1.0e-7, method='false-position', verbose=False):

        self.maximum_iterations = maximum_iterations
        self.relative_tolerance = relative_tolerance
        self.method = method
        self.verbose = verbose

        # handle for pymbar.BAR object
        self._bar = None

    def fit(self, u_nk):
        """
        Compute overlap matrix of reduced potentials using
        Bennett acceptance ratio.

        Parameters
        ----------
        u_nk : DataFrame 
            u_nk[n,k] is the reduced potential energy of uncorrelated
            configuration n evaluated at state k.

        """
        # sort by state so that rows from same state are in contiguous blocks
        u_nk = u_nk.sort_index(level=u_nk.index.names[1:])

        # get a list of the lambda states
        self.states_ = u_nk.columns.values.tolist()

        # group u_nk by lambda states
        groups = u_nk.groupby(level=u_nk.index.names[1:])
        N_k = [(len(groups.get_group(i)) if i in groups.groups else 0) for i in u_nk.columns]

        # Now get free energy differences and their uncertainties for each step
        deltas = np.array([])
        d_deltas = np.array([])
        for k in range(len(N_k) - 1):
            # get us from lambda step k
            uk = groups.get_group(self.states_[k])
            # get w_F
            w_f = uk.iloc[:, k+1] - uk.iloc[:, k]

            # get us from lambda step k+1
            uk1 = groups.get_group(self.states_[k+1])
            # get w_R
            w_r = uk1.iloc[:, k] - uk1.iloc[:, k+1]

            # now determine df and ddf using pymbar.BAR
            df, ddf = BAR_(w_f, w_r,
                             method=self.method,
                             maximum_iterations=self.maximum_iterations,
                             relative_tolerance=self.relative_tolerance,
                             verbose=self.verbose)

            deltas = np.append(deltas, df)
            d_deltas = np.append(d_deltas, ddf**2)

        # build matrix of deltas between each state
        adelta = np.zeros((len(deltas) + 1, len(deltas) + 1))
        ad_delta = np.zeros_like(adelta)

        for j in range(len(deltas)):
            out = []
            dout = []
            for i in range(len(deltas) - j):
                out.append(deltas[i:i + j + 1].sum())

                # See https://github.com/alchemistry/alchemlyb/pull/60#issuecomment-430720742
                # Error estimate generated by BAR ARE correlated

                # Use the BAR uncertainties between two neighbour states
                if j == 0:
                    dout.append(d_deltas[i:i + j + 1].sum())
                # Other uncertainties are unknown at this point
                else:
                    dout.append(float('NaN'))

            adelta += np.diagflat(np.array(out), k=j + 1)
            ad_delta += np.diagflat(np.array(dout), k=j + 1)

        # yield standard delta_f_ free energies between each state
        self.delta_f_ = pd.DataFrame(adelta - adelta.T,
                                     columns=self.states_,
                                     index=self.states_)

        # yield standard deviation d_delta_f_ between each state
        self.d_delta_f_ = pd.DataFrame(np.sqrt(ad_delta + ad_delta.T),
                                       columns=self.states_,
                                       index=self.states_)

        return self

    def predict(self, u_ln):
        pass
