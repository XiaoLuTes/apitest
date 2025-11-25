import sys
import pytest

def main():
    """只运行测试，不生成报告"""
    exit_code = pytest.main()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())

# if __name__ == '__main__':
#     pytest.main()
#     os.system("allure generate ./reports/temp -o ./reports/allure-reports --clean")
