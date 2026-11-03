# Keep simultaneous editor builds from overwriting the same PDF and references.
use Fcntl qw(LOCK_EX);

# latexmk evaluates this file inside a function; retain the handle until exit.
our $iceic2027_build_lock;
open($iceic2027_build_lock, '>>', '.latexmk.lock')
    or die "Cannot open the LaTeX build lock: $!\n";
flock($iceic2027_build_lock, LOCK_EX)
    or die "Cannot acquire the LaTeX build lock: $!\n";
