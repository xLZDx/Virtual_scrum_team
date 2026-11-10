def compute(task):
    try:
        return task()
    finally:
        print("done")
