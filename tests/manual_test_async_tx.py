# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 EdNoepel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import logging
import os
import sys
import threading
import time

from pymaker import Address, web3_via_http
from pymaker.deployment import DssDeployment
from pymaker.gas import FixedGasPrice, GeometricGasPrice
from pymaker.keys import register_keys
from pymaker.numeric import Wad

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
# reduce logspew
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger("web3").setLevel(logging.INFO)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)

pool_size = int(sys.argv[3]) if len(sys.argv) > 3 else 10
web3 = web3_via_http(endpoint_uri=os.environ['ETH_RPC_URL'], http_pool_size=pool_size)
web3.eth.defaultAccount = sys.argv[1]   # ex: 0x0000000000000000000000000000000aBcdef123
register_keys(web3, [sys.argv[2]])      # ex: key_file=~keys/default-account.json,pass_file=~keys/default-account.pass


mcd = DssDeployment.from_node(web3)
our_address = Address(web3.eth.defaultAccount)

collateral = mcd.collaterals['ETH-A']
ilk = collateral.ilk
collateral.approve(our_address)

GWEI = 1000000000
fast_gas = GeometricGasPrice(initial_price=int(1 * GWEI), every_secs=30, max_price=2000 * GWEI)
slow_gas = GeometricGasPrice(initial_price=int(0.8 * GWEI), every_secs=30, max_price=2000 * GWEI)


class TestApp:
    def __init__(self):
        self.wrap_amount = Wad(12)

    def main(self):
        self.startup()
        self.test_replacement()
        self.test_simultaneous()
        self.shutdown()

    def startup(self):
        logging.info(f"Wrapping {self.wrap_amount} ETH")
        assert collateral.gem.deposit(self.wrap_amount).transact(gas_price=fast_gas)

    def test_replacement(self):
        first_tx = collateral.adapter.join(our_address, Wad(4))
        logging.info(f"Submitting first TX with gas price deliberately too low")
        self._run_future(first_tx.transact_async(gas_price=slow_gas))
        time.sleep(2)

        second_tx = collateral.adapter.join(our_address, Wad(6))
        logging.info(f"Replacing first TX with legitimate gas price")
        second_tx.transact(replace=first_tx, gas_price=FixedGasPrice(2*GWEI))

        assert first_tx.replaced

    def test_simultaneous(self):
        self._run_future(collateral.adapter.join(our_address, Wad(1)).transact_async(gas_price=slow_gas))
        self._run_future(collateral.adapter.join(our_address, Wad(5)).transact_async(gas_price=slow_gas))
        asyncio.sleep(6)

    def shutdown(self):
        logging.info(f"Exiting {ilk.name} from our urn")
        balance = mcd.vat.gem(ilk, our_address)
        if balance < Wad(100):  # this account's tiny vault came from this test
            assert collateral.adapter.exit(our_address, balance).transact(gas_price=fast_gas)
        else:  # the account has a vault for some other reason
            assert collateral.adapter.exit(our_address, Wad(12)).transact(gas_price=fast_gas)
        logging.info(f"Balance is {mcd.vat.gem(ilk, our_address)} {ilk.name}")
        logging.info(f"Unwrapping {self.wrap_amount} ETH")
        assert collateral.gem.withdraw(self.wrap_amount).transact(gas_price=fast_gas)

    @staticmethod
    def _run_future(future):
        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                asyncio.get_event_loop().run_until_complete(future)
            finally:
                loop.close()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


if __name__ == '__main__':
    TestApp().main()
