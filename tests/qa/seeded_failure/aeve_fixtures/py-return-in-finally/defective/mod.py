def compute(task):
    try:
        return task()
    finally:
        return 0
