from typing import Any, Union, cast
from boa3.builtin.nativecontract.neo import NEO as NEO_TOKEN
from boa3.builtin.compile_time import NeoMetadata, metadata, public
from boa3.builtin.contract import NeoAccountState, abort, Nep17TransferEvent
from boa3.builtin.interop import runtime, storage, blockchain, contract
from boa3.builtin.interop.blockchain import Transaction
from boa3.builtin.interop.runtime import script_container
from boa3.builtin.interop.contract import GAS as GAS_SH, NEO as NEO_SH, call_contract
from boa3.builtin.nativecontract.contractmanagement import ContractManagement
from boa3.builtin.type import UInt160, UInt256, ECPoint, helper

# Metadata for the token
@metadata
def manifest_metadata() -> NeoMetadata:
    meta = NeoMetadata()
    meta.supported_standards = ['NEP-17']
    meta.add_permission(methods=['onNEP17Payment'])
    meta.add_permission(contract='0xef4073a0f2b305a38ec4050e4d3d28bc40ea63f5')
    meta.author = "Denis"
    meta.email = "denis.neo.hk@gmail.com"
    meta.description = "NeoDeposit"
    return meta

# Token details
TOKEN_NAME = 'NeoDeposit'
TOKEN_SYMBOL = 'NeoDep'
TOKEN_DECIMALS = 0
INITIAL_SUPPLY = 0
MAX_SUPPLY = 10_000_000

# Events
on_transfer = Nep17TransferEvent

# Storage keys
TOTAL_SUPPLY_KEY = b'total_supply'
BALANCE_PREFIX = b'balance_'



# -------------------------------------------
# Methods
# -------------------------------------------

@public(safe=True)
def symbol() -> str:
    return TOKEN_SYMBOL

@public(safe=True)
def decimals() -> int:
    return TOKEN_DECIMALS

@public(name='totalSupply', safe=True)
def totalSupply() -> int:
    return helper.to_int(storage.get(TOTAL_SUPPLY_KEY))

@public(name='maxSupply', safe=True)
def maxSupply() -> int:
    return MAX_SUPPLY

# Get the balance of an account
@public(name='balanceOf', safe=True)
def balanceOf(account: UInt160) -> int:
    return helper.to_int(storage.get(BALANCE_PREFIX + account))

def post_transfer(from_address: Union[UInt160, None], to_address: Union[UInt160, None], amount: int, data: Any, call_onPayment:bool):
    """
    Checks if the one receiving NEP17 tokens is a smart contract and if it's one the onPayment method will be called
    """
    if call_onPayment:
        if to_address is not None:
            contract = ContractManagement.get_contract(to_address)
            if contract is not None:
                call_contract(to_address, 'onNEP17Payment', [from_address, amount, data])

# Transfer tokens from one account to another
@public(name='transfer')
def transfer(from_address: UInt160, to_address: UInt160, amount: int, data: Any) -> bool:
    assert amount > 0, "Amount must be greater than 0"
    assert runtime.check_witness(from_address), "Invalid witness"
    assert balanceOf(from_address) >= amount, "Insufficient balance"

    storage.put(BALANCE_PREFIX + from_address, balanceOf(from_address) - amount)
    storage.put(BALANCE_PREFIX + to_address, balanceOf(to_address) + amount)
    on_transfer(from_address, to_address, amount)
    post_transfer(from_address, to_address, amount, data, True)

    return True


@public
def mint(from_address: UInt160, amount: int):
    assert amount > 0, "Amount must be greater than 0"
    assert len(from_address) == 20,  "Invalid address"

    # Mint n (amount) new tokens
    #check updated supply < MAX_SUPPLY
    if totalSupply()+amount <= maxSupply():
        storage.put(TOTAL_SUPPLY_KEY, totalSupply() + amount)
        storage.put(BALANCE_PREFIX + from_address, balanceOf(from_address) + amount)

        on_transfer(None, from_address, amount)
        post_transfer(None, from_address, amount, None, True)
    else:
        abort()

@public
def burn(from_address: UInt160, amount: int):
    assert amount > 0, "Amount must be greater than 0"
    assert len(from_address) == 20,  "Validate from_address"

    # Burn the tokens
    if runtime.check_witness(from_address):
        storage.put(TOTAL_SUPPLY_KEY, totalSupply() - amount)
        if balanceOf(from_address) == amount:
            storage.delete(BALANCE_PREFIX + from_address)
        else:
            storage.put(BALANCE_PREFIX + from_address, balanceOf(from_address) - amount)
        
        on_transfer(from_address, None, amount)
        post_transfer(from_address, None, amount, None, False)

        NEO_TOKEN.transfer(runtime.executing_script_hash, from_address, amount)

       

        
@public
def onNEP17Payment(from_address: UInt160, amount: int, data: Any):
    # Mint 1:1 tokens for Neo if Neo is being sent to the contract

    assert len(from_address) == 20,  "Invalid address"

    if runtime.calling_script_hash == NEO_SH:
        mint(from_address,amount)
    else:
        abort()

# Vote for a consensus node
@public
def vote_for_node(node_public_key: ECPoint) -> bool:
    # Ensure the caller is authorized (e.g., the contract owner or a specific address)
    assert runtime.check_witness(runtime.executing_script_hash), "Unauthorized"

    # Get the NEO token contract
    neo_contract = NEO_SH

    # Call the NEO contract's `vote` method
    # Parameters: voter (contract's address), node_public_key
    if call_contract(UInt160(neo_contract),'vote', [runtime.executing_script_hash, node_public_key]):
        return True
    else:
        return False

# Revoke the contract's vote
@public
def revoke_vote() -> bool:
    # Ensure the caller is authorized (e.g., the contract owner or a specific address)
    assert runtime.check_witness(runtime.executing_script_hash), "Unauthorized"

    # Get the NEO token contract
    neo_contract = NEO_SH

    # Call the NEO contract's `vote` method with None to revoke the vote
    if call_contract(UInt160(neo_contract),'vote', [runtime.executing_script_hash, None]):
        return True
    else:
        return False


# Initialize the contract
@public
def _deploy(data: Any, update: bool):
    if not update:
        container: Transaction = runtime.script_container
        storage.put(TOTAL_SUPPLY_KEY, INITIAL_SUPPLY)
        storage.put(BALANCE_PREFIX + container.sender, INITIAL_SUPPLY)
        on_transfer(None, container.sender, INITIAL_SUPPLY)