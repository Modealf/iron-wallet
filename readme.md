# Designing an investment wallet  

![Make it Rain](./dev_setup/img/make_it.jpg "Make it rain")


Design an investment wallet system for a company called `IronWallet` that incorporates a payment gateway and utilizes an omnibus account. How would you approach the architectural design to ensure seamless and secure user transactions?

### Objective

Demonstrate your skills in managing state, ensuring idempotency, and addressing common distributed system challenges. This exercise involves architecting a solution for an investment wallet system that supports two core functions: **Top-Up** (funding a wallet) and **Fund Transfer** (from a user’s bank to the investment wallet).

### Scope

Your task is to design, implement, and explain a high-level system architecture for the following components, with a focus on ensuring consistent state, managing concurrency, and maintaining idempotency across services:

1. **Top-Up (Fund Wallet)**
2. **Fund Transfer (from User Bank to Investment Wallet)**

### Services Involved

1. **IronWallet API Gateway**: A gateway service that abstracts IronWallet’s internal services, serving client applications (Mobile/Web apps).
2. **Investment-Wallet Service**: Manages wallet-related operations, including funding and balance updates.
3. **Payment Gateway Service**: Integrates with external payment providers to process payments.
4. **Omnibus Service**: Handles operations related to omnibus (virtual accounts) and integrates with omnibus providers.

### Requirements

#### 1. Business Logic for Top-Up

1. A client (Mobile/Web app) initiates a fund request through the **IronWallet API Gateway**.
2. The gateway redirects the request to the **Investment-Wallet Service**.
3. The **Investment-Wallet Service** communicates with the **Payment Gateway Service**, which sends the request to an external payment provider.
4. Once the payment is processed, the provider transfers the amount to the **IronWallet Omnibus Account** and sends a settlement document to the **Omnibus Service** via a webhook.
5. The **Omnibus Service** creates an account statement containing the payment amount and transfer details.
6. The **Omnibus Service** processes the settlement, reconciles virtual account balances, and updates the **Investment-Wallet Service** with the latest transaction.
7. The **Investment-Wallet Service** reflects the fund request status as “Paid.”

#### 2. Business Logic for Fund Transfer

1. A user retrieves their virtual IBAN from the **IronWallet App** and initiates a local bank transfer.
2. The local bank processes the transfer to the **Omnibus Account**.
3. The **Omnibus Service** generates an account statement that includes the virtual IBAN and transfer details.
4. The **Omnibus Service** reconciles virtual account balances and notifies the **Investment-Wallet Service** of the latest transaction.
5. The **Investment-Wallet Service** reflects the fund transfer status as “Paid.”

### Deliverables

1. **System Architecture**: Present a high-level design showcasing the system’s architecture. Include each component and describe the data flow for handling user requests, payments, and transfers.
2. **Concurrency and Idempotency Solutions**:
    - Describe your approach to handling transaction concurrency, ensuring each request is processed only once, and managing partial failures.
    - Explain strategies to maintain idempotency and reliability for each service interaction.
3. **Proof of Concept (POC)**:
    - Implement a basic POC demonstrating API communication between the **Investment-Wallet Service**, **Payment Gateway Service**, and **Omnibus Service**.
    - Include at least one example for each key operation (e.g., a sample top-up and a fund transfer) to show how you would handle state transitions, retries, and idempotency.
4. **Considerations for Edge Cases**:
    - Document any edge cases (e.g., delayed bank transfers or conflicting top-up requests) and explain how you would address them.
5. **Future Improvements**:
    - State any future work, stuff you wanted to work on but couldn't due to time limitations or stuff you experimented with but discarded eventually

### Assumptions During POC Implementations

- Assume that users are already authenticated and authorized to use the investment-wallet services.
- Since your system will need a payment gateway/ omnibus provider, it is optional to read about the below APIs for better understanding and mocking
    - [ANB statement API](https://developer.anb.com.sa/apis/api/account-statement/doc#operation/statement)
    - [Moyasar for payment gateway](https://docs.moyasar.com/)

## Running the POC Template

> 💡 Please note that this is an optional template; you can make your own if you want to
> 

### Prerequisites

- Docker
- Poetry

### Setting up Dependencies

- Run Docker Dependencies:

```shell
make up
```

- Install Python dependencies

```shell
make install
```

### Starting the services

The template uses Poe to manage commands; each time, the file has a section where you can define shortcuts. For example, for running the gateway service, do the following
start Gateway service

```shell
cd /repos/gateway
poetry run poe api_service
```
