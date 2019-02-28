args <- commandArgs(T)

bundle_file <- args[1]
if (!file.exists(bundle_file)) {
    warning(sprintf('No such file: %s', bundle_file))
    quit(save = "no", status = 1, runLast = FALSE)
}

lib_dir <- "/tmp"

if (!require('packrat')) {
    install.packages('packrat')
}

packrat::unbundle(bundle_file, where=lib_dir)

# Copy all packrat lib files to the root directory of a shiny app
# R session will activate packrat lib automatically.
# More details see https://groups.google.com/forum/#!topic/packrat-discuss/66OJRXOqH9o.
# The name of bundle_file may be not same with packrat bundle name. Get bundle name from tar package is more robust.
bundle_name <- unlist(strsplit(untar(bundle_file, list=TRUE)[1], "[/]"))[1]
packrat_lib <- sprintf("/tmp/%s", bundle_name)
sprintf('Copy packrat lib from %s to %s', packrat_lib, '/srv/shiny-server/')
packrat_lib_profile <- sprintf('%s/.Rprofile', packrat_lib)
packrat_lib_packrat <- sprintf('%s/packrat', packrat_lib)
file.copy(packrat_lib_profile, '/srv/shiny-server/', overwrite = TRUE, recursive = TRUE, copy.mode = TRUE, copy.date = FALSE)
file.copy(packrat_lib_packrat, '/srv/shiny-server/', overwrite = TRUE, recursive = TRUE, copy.mode = TRUE, copy.date = FALSE)
print('Copied.')
