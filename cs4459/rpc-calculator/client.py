import grpc
import sys
import time
import random
from datetime import datetime
sys.path.append('./generated')
import calculator_pb2
import calculator_pb2_grpc


# Configuration Constants (DO NOT CHANGE)
DEFAULT_TIMEOUT = 2  # seconds
MAX_RETRIES = 3      # retries for divide only


def create_client_stub(address='localhost:50051'):
    """
    Create and return a Calculator stub.
    """
    channel = grpc.insecure_channel(address)
    stub = calculator_pb2_grpc.CalculatorStub(channel)
    return stub


def add(stub, a, b):
    """
    Add two numbers. No retry logic.
    """
    request = calculator_pb2.BinaryOperation(a=a, b=b)
    return stub.Add(request, timeout=DEFAULT_TIMEOUT)


def subtract(stub, a, b):
    """
    Subtract two numbers. No retry logic.
    """
    request = calculator_pb2.BinaryOperation(a=a, b=b)
    return stub.Subtract(request, timeout=DEFAULT_TIMEOUT)


def multiply(stub, a, b):
    """
    Multiply two numbers. No retry logic.
    """
    request = calculator_pb2.BinaryOperation(a=a, b=b)
    return stub.Multiply(request, timeout=DEFAULT_TIMEOUT)


def divide(stub, a, b):
    """
    Divide two numbers with retry logic.
    """
    request = calculator_pb2.BinaryOperation(a=a, b=b)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = stub.Divide(request, timeout=DEFAULT_TIMEOUT)
            return response.value

        except grpc.RpcError as e:
            # not retrying division by zero
            if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                return "INVALID_ARGUMENT"

            # retry cases
            if e.code() in (
                grpc.StatusCode.DEADLINE_EXCEEDED,
                grpc.StatusCode.UNAVAILABLE
            ):
                if attempt == MAX_RETRIES:
                    if e.code() == grpc.StatusCode.UNAVAILABLE:
                        return "SERVER_UNAVAILABLE"
                    else:
                        return "TIMEOUT_EXCEEDED"

                backoff = (2 ** (attempt - 1)) + random.uniform(0, 0.1)
                time.sleep(backoff)
            else:
                # any other unexpected error
                return f"ERROR: {e.code().name}"


def main():
    """Main function to test the calculator."""
    stub = create_client_stub()

    try:
        print("Add:", add(stub, 10, 5).value)
        print("Subtract:", subtract(stub, 10, 5).value)
        print("Multiply:", multiply(stub, 10, 5).value)

        print("Divide:", divide(stub, 10, 5))
        print("Divide by zero:", divide(stub, 10, 0))

    except grpc.RpcError as e:
        print("RPC failed:", e)


if __name__ == '__main__':
    main()
