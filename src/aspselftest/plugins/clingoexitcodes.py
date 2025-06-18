
import enum


# ExitCode, see clasp_app.h
class ExitCode(enum.IntEnum):
    UNKNOWN   =   0  #/*!< Satisfiability of problem not known; search not started.   */
    INTERRUPT =   1  #/*!< Run was interrupted.                                       */
    SAT       =  10  #/*!< At least one model was found.                              */
    EXHAUST   =  20  #/*!< Search-space was completely examined.                      */
    MEMORY    =  33  #/*!< Run was interrupted by out of memory exception.            */
    ERROR     =  65  #/*!< Run was interrupted by internal error.                     */
    NO_RUN    = 128  #/*!< Search not started because of syntax or command line error.*/
