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

import logging
import os
import sys
from web3 import Web3, HTTPProvider

from pymaker import Address, Transact
from pymaker.deployment import DssDeployment
from pymaker.keys import register_keys

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

endpoint_uri = sys.argv[1]              # ex: https://localhost:8545
web3 = Web3(HTTPProvider(endpoint_uri=os.environ['ETH_RPC_URL'], request_kwargs={"timeout": 30}))
web3.eth.defaultAccount = sys.argv[1]   # ex: 0x0000000000000000000000000000000aBcdef123
register_keys(web3, [sys.argv[2]])      # ex: key_file=~keys/default-account.json,pass_file=~keys/default-account.pass

mcd = DssDeployment.from_node(web3)
our_address = Address(web3.eth.defaultAccount)

# Allow bad transactions to go to the chain
Transact.gas_estimate_for_bad_txs = 20000

# Submit a bad transaction
tx = mcd.vat.init(mcd.collaterals['BAT-A'].ilk)
tx.transact()  # Should fail with "Vat/ilk-already-init"

print(tx.revert_reason())
