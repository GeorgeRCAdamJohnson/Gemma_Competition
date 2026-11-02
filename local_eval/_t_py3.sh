which python3
python3 -c "import sys; print(sys.version); print(sys.stdout.isatty())"
echo "exit=$?"
python3 -c "import sys; print(f'isatty: {getattr(sys.stdout, \"isatty\", None)}')"
echo "exit=$?"
