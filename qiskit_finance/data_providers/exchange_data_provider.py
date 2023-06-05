# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2022.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

""" Exchange data provider. """

from typing import Union, List
import logging
import datetime
import nasdaqdatalink

from ._base_data_provider import BaseDataProvider, StockMarket
from ..exceptions import QiskitFinanceError

logger = logging.getLogger(__name__)


class ExchangeDataProvider(BaseDataProvider):
    """Exchange data provider.

    Please see:
    https://github.com/Qiskit/qiskit-finance/blob/main/docs/tutorials/11_time_series.ipynb
    for instructions on use, which involve obtaining a Nasdaq Data Link access token.
    """

    def __init__(
        self,
        token: str,
        tickers: Union[str, List[str]],
        stockmarket: StockMarket = StockMarket.LONDON,
        start: datetime.datetime = datetime.datetime(2016, 1, 1),
        end: datetime.datetime = datetime.datetime(2016, 1, 30),
    ) -> None:
        """
        Args:
            token: Nasdaq Data Link access token
            tickers: tickers
            stockmarket: LONDON, EURONEXT, or SINGAPORE
            start: first data point
            end: last data point precedes this date

        Raises:
            QiskitFinanceError: provider doesn't support given stock market
        """
        super().__init__()
        self._tickers = []  # type: Union[str, List[str]]
        if isinstance(tickers, list):
            self._tickers = tickers
        else:
            self._tickers = tickers.replace("\n", ";").split(";")
        self._n = len(self._tickers)

        if stockmarket not in [
            StockMarket.LONDON,
            StockMarket.EURONEXT,
            StockMarket.SINGAPORE,
        ]:
            msg = "ExchangeDataProvider does not support "
            msg += stockmarket.value
            msg += " as a stock market."
            raise QiskitFinanceError(msg)

        # This is to aid serialization; string is ok to serialize
        self._stockmarket = str(stockmarket.value)

        self._token = token
        self._tickers = tickers
        self._start = start.strftime("%Y-%m-%d")
        self._end = end.strftime("%Y-%m-%d")

    def run(self) -> None:
        """
        Loads data, thus enabling get_similarity_matrix and get_covariance_matrix
        methods in the base class.
        """
        nasdaqdatalink.ApiConfig.api_key = self._token
        self._data = []
        stocks_notfound = []
        stocks_forbidden = []
        for _, ticker_name in enumerate(self._tickers):
            stock_data = None
            name = f"{self._stockmarket}/{ticker_name}"
            try:
                stock_data = nasdaqdatalink.get(name, start_date=self._start, end_date=self._end)
            except nasdaqdatalink.AuthenticationError as ex:
                logger.debug(ex, exc_info=True)
                raise QiskitFinanceError("Nasdaq Data Link invalid token.") from ex
            except nasdaqdatalink.LimitExceededError as ex:
                logger.debug(ex, exc_info=True)
                raise QiskitFinanceError("Nasdaq Data Link limit exceeded.") from ex
            except nasdaqdatalink.NotFoundError as ex:
                logger.debug(ex, exc_info=True)
                stocks_notfound.append(name)
                continue
            except nasdaqdatalink.ForbiddenError as ex:
                logger.debug(ex, exc_info=True)
                stocks_forbidden.append(name)
                continue
            except nasdaqdatalink.DataLinkError as ex:
                logger.debug(ex, exc_info=True)
                raise QiskitFinanceError(f"Nasdaq Data Link Error for '{name}'.") from ex
            try:
                self._data.append(stock_data["Close"])
            except KeyError as ex:
                raise QiskitFinanceError(f"Cannot parse Nasdaq Data Link '{name}' output.") from ex

        if stocks_notfound or stocks_forbidden:
            err_msg = f"Stocks not found: {stocks_notfound}. " if stocks_notfound else ""
            if stocks_forbidden:
                err_msg += (
                    "You do not have permission to view this data. "
                    f"Please subscribe to this database: {stocks_forbidden}"
                )
            raise QiskitFinanceError(err_msg)
