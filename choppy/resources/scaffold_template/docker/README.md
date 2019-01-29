## Docker 镜像说明
此 Choppy App 共包含 2 个 Docker 镜像，分别为 my_program_1 和 my_program_2 的运行环境。相关的代码及其Dockerfile详解见各程序目录下的README.md.

若采用`choppy build`命令构建 docker 镜像，则 Dockerfile 会自动生成。使用方式：
1. 切换目录至docker
2. 进入代码所在目录，以 my_program_1 为例
   ```
   cd my_program_1
   choppy build my_program_1 0.1.0 --parser r --main-program maftools_general.R --dep bioconductor-maftools:1.6.15
   ```