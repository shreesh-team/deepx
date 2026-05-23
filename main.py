from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello From FastAPI"}


# def main():
#     print("Hello from deepx!")


# if __name__ == "__main__":
#     main()
