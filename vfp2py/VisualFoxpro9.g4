grammar VisualFoxpro9
 ;

preprocessorCode
 : (preprocessorLine | nonpreprocessorLine)*?
 ;

preprocessorLine
 : '#' (IF expr | IFDEF identifier) NL 
           ifBody=preprocessorCode
  ('#' ELSE NL
           elseBody=preprocessorCode)?
   '#' ENDIF lineEnd #preprocessorIf
 | '#' DEFINE identifier .*? lineEnd #preprocessorDefine
 | '#' UNDEFINE identifier lineEnd #preprocessorUndefine
 | '#' INCLUDE specialExpr lineEnd #preprocessorInclude
 ;

nonpreprocessorLine
 : LINECOMMENT 
 | lineEnd
 | {_input.enableChannel(1);} .*? lineEnd {_input.disableChannel(1);}
 ;

prg
 : line* (classDef | funcDef | lineComment)*
 ;

lineComment
 : LINECOMMENT
 ;

line
 : controlStmt
 | cmdStmt
 | lineComment
 ;

lineEnd
 : NL
 | EOF
 ;

lines
 : line*?
 ;

classDefStart
 : DEFINE CLASS identifier (AS identifier)? NL
 ;

classDef
 : classDefStart classDefStmt* ENDDEFINE lineEnd
 ;

classDefStmt
 : ADD OBJECT identifier AS idAttr (WITH idAttr '=' expr (',' idAttr '=' expr)*)? NL #classDefAddObject
 | assign NL #classDefAssign
 | funcDef #classDefFuncDef
 | lineComment #classDefLineComment
 ;

funcDefStart
 : (PROCEDURE | FUNCTION) idAttr ('(' parameters? ')')? NL parameterDef?
 ;

funcDefEnd
 : (ENDPROC | ENDFUNC) lineEnd
 ;

parameterDef
 : (LPARAMETER | LPARAMETERS | PARAMETERS) parameters NL
 ;

funcDef
 :  funcDefStart lines funcDefEnd?
 ;

parameter
 : idAttr (AS idAttr)?
 ;

parameters
 : parameter (',' parameter)*
 ;

ifStart
 : IF expr THEN? NL
 ;

ifStmt
 : ifStart ifBody=lines (ELSE NL elseBody=lines)? ENDIF lineEnd
 ;

forStart
 : FOR idAttr '=' loopStart=expr TO loopStop=expr (STEP loopStep=expr)? NL
 ;

forEnd
 : (ENDFOR | NEXT idAttr? lineEnd)
 ;

forStmt
 : forStart lines forEnd lineEnd
 ;

caseExpr
 : CASE expr NL
 ;

singleCase
  : caseExpr lines
 ;

otherwise
 : OTHERWISE NL lines
 ;

caseElement
 : lineComment
 | singleCase
 ;

caseStmt
 : DO CASE NL caseElement* otherwise? lineComment* ENDCASE lineEnd
 ;

whileStart
 : DO? WHILE expr NL
 ;

whileStmt
 : whileStart line* ENDDO lineEnd
 ;

withStmt
 : WITH idAttr NL line* ENDWITH lineEnd
 ;

scanStmt
 : SCAN NL line* ENDSCAN
 ;

breakLoop
 : EXIT NL
 ;

continueLoop
 : LOOP NL
 ;

controlStmt
 : whileStmt
 | ifStmt
 | caseStmt
 | forStmt
 | withStmt
 | scanStmt
 | breakLoop
 | continueLoop
 ;

cmdStmt
 : (cmd | setup) lineEnd
 ;

cmd
 : funcDo
 | assign
 | declaration
 | printStmt
 | waitCmd
 | filesystemCmd
 | returnStmt
 | quit
 | release
 | setup
 | otherCmds
 | '='? expr
 ;

release
 : RELEASE (ALL | vartype=(PROCEDURE|CLASSLIB)? args)
 ;

otherCmds
 : ON KEY (LABEL identifier ('+' identifier)?)? cmd #onKey
 | PUSH KEY CLEAR? #pushKey
 | POP KEY ALL? #popKey
 | KEYBOARD expr PLAIN? CLEAR? #keyboard

 | DEFINE MENU identifier (BAR (AT LINE NUMBER_LITERAL)?) (IN (WINDOW? identifier | SCREEN))? NOMARGIN? #defineMenu
 | DEFINE PAD identifier OF expr PROMPT expr (AT NUMBER_LITERAL ',' NUMBER_LITERAL)?
         (BEFORE identifier | AFTER identifier)? (NEGOTIATE identifier (',' identifier)?)?
         (FONT identifier (',' NUMBER_LITERAL (',' STRING_LITERAL (',' identifier)?)?)?)? (STYLE identifier)?
         (MESSAGE expr)? (KEY identifier ('+' identifier)? (',' STRING_LITERAL)?)? (MARK identifier)?
         (SKIPKW (FOR expr)?)? (COLOR SCHEME NUMBER_LITERAL)? #definePad
 | DEFINE POPUP identifier SHADOW? MARGIN? RELATIVE? (COLOR SCHEME NUMBER_LITERAL)? #definePopup
 | DEFINE BAR NUMBER_LITERAL OF identifier PROMPT expr (MESSAGE expr)? #defineBar
 | ON PAD identifier OF identifier (ACTIVATE (POPUP | MENU) identifier)? #onPad
 | ON BAR NUMBER_LITERAL OF identifier (ACTIVATE (POPUP | MENU) identifier)? #onBar
 | ON SELECTION BAR NUMBER_LITERAL OF identifier cmd #onSelectionBar
 | ACTIVATE WINDOW (parameters | ALL) (IN (WINDOW? identifier | SCREEN))? (BOTTOM | TOP | SAME)? NOSHOW? #activateWindow
 | ACTIVATE MENU identifier NOWAIT? (PAD identifier)? #activateMenu
 | DEACTIVATE MENU (parameters | ALL) #deactivateMenu


 | CREATE (TABLE|DBF) expr FREE? '(' identifier identifier arrayIndex (',' identifier identifier arrayIndex)* ')' #createTable
 | SELECT (tablename=expr | (DISTINCT? (args | '*') (FROM fromexpr=expr)? (WHERE whereexpr=expr)? (INTO TABLE intoexpr=expr)? (ORDER BY orderbyid=identifier)?)) #select
 | USE (SHARED | EXCL | EXCLUSIVE)? name=expr? IN workArea=expr? (SHARED | EXCL | EXCLUSIVE)? (ALIAS identifier)? #use
 | LOCATE (FOR expr)? (WHILE expr)? NOOPTIMIZE? #locate
 | REPLACE scopeClause? idAttr WITH expr (FOR expr)? #replace
 | INDEX ON expr (TAG | TO) expr (COMPACT | ASCENDING | DESCENDING)? ( UNIQUE | CANDIDATE)? ADDITIVE? #indexOn
 | COUNT scopeClause? ((FOR expr) | (WHILE expr) | (TO expr))* NOOPTIMIZE? #count
 | SUM scopeClause? expr (FOR expr | TO idAttr | NOOPTIMIZE)+ #sum
 | DELETE scopeClause? (FOR expr)? (WHILE expr)? (IN expr)? NOOPTIMIZE? #deleteRecord
 | APPEND (BLANK? (IN idAttr)? NOMENU? | FROM specialExpr) #append
 | SKIPKW expr (IN expr)? #skipRecord
 | SEEK expr #seekRecord
 | (GO | GOTO) (TOP | BOTTOM | RECORD? expr) (IN idAttr)? #goRecord
 | COPY STRUCTURE? TO expr #copyTo
 | ZAP (IN expr)? #zapTable

 | CLOSE ((DATABASES | INDEXES | TABLES) ALL? | ALL) #closeStmt
 | READ EVENTS #readEvent
 | CLEAR (ALL | DLLS args | MACROS | EVENTS) #clearStmt
 | DO FORM specialExpr #doForm
 | REPORT FORM expr NOEJECT? TO PRINTER PROMPT? NOCONSOLE #report
 | DECLARE datatype? identifier IN expr (AS identifier)? (datatype '@'? identifier? (',' datatype '@'? identifier?)*)? #dllDeclare
 | NODEFAULT #nodefault
 ;

printStmt
 : '?' args?
 ;

waitCmd
 : WAIT (TO toExpr=expr | WINDOW (AT atExpr1=expr ',' atExpr2=expr)? | NOWAIT | CLEAR | NOCLEAR | TIMEOUT timeout=expr | message=expr)*
 ;

filesystemCmd
 : (ERASE | DELETE FILE) (specialExpr|'?') RECYCLE? #deleteFile
 | (RENAME | COPY FILE) specialExpr TO specialExpr #copyMoveFile
 | (MD | MKDIR | RD | RMDIR) specialExpr #addRemoveDirectory
 ;

quit
 : QUIT
 ;

returnStmt
 : RETURN expr?
 ;

setup
 : onError
 | setStmt
 | onShutdown
 ;

onError
 : ON ERROR cmd?
 ;

onShutdown
 : ON SHUTDOWN cmd?
 ;

setStmt
 : SET setCmd
 ;

setCmd
 : ALTERNATE (ON | OFF | TO specialExpr ADDITIVE?)
 | BELL (ON | OFF | TO specialExpr)
 | CENTURY (ON | OFF | TO (expr (ROLLOVER expr)?)?) 
 | CLASSLIB TO specialExpr ADDITIVE?
 | CLOCK (ON | OFF | STATUS | TO (expr ',' expr)?)
 | CURSOR (ON | OFF)
 | DATE TO? identifier
 | DELETED (ON | OFF)
 | EXACT (ON | OFF)
 | FILTER TO expr (IN specialExpr)?
 | LIBRARY TO (specialExpr ADDITIVE?)
 | MEMOWIDTH TO expr
 | NEAR (ON | OFF)
 | NOTIFY CURSOR? (ON | OFF)
 | ORDER TO (specialExpr | TAG? specialExpr (OF specialExpr)? (IN specialExpr)? (ASCENDING | DESCENDING)?)?
 | PRINTER (ON PROMPT? | OFF | TO (expr ADDITIVE? | DEFAULT | NAME expr)?)
 | PROCEDURE TO specialExpr (',' specialExpr)* ADDITIVE?
 | REFRESH TO expr (',' expr)?
 | STATUS (ON | OFF)
 | STATUS BAR (ON | OFF)
 | SYSMENU (ON | OFF | TO (expr | DEFAULT)? | SAVE | NOSAVE)
 | TYPEAHEAD TO expr
 | UNIQUE (ON | OFF)
 ;

declaration
 : (PUBLIC|PRIVATE|LOCAL) (parameters | ARRAY? identifier arrayIndex)
 | (DIMENSION | DEFINE) identifier arrayIndex
 ;

args
 : expr (',' expr)*
 ;

funcDo
 : DO idAttr (IN specialExpr)? (WITH args)?
 ;

reference
 : '@' idAttr
 ;

argReplace
 : '&' identifier
 ;

expr
 : '(' expr ')' #subExpr
 | '-' expr #unaryNegation
 | ('!'|NOT) expr #booleanNegation
 | expr ('*' '*'|'^') expr #power
 | expr op=('*'|'/') expr #multiplication
 | expr '%' expr #modulo
 | expr op=('+'|'-') expr #addition
 | expr op=('=='|NOTEQUALS|'='|'#'|'>'|'>='|'<'|'<='|'$') expr #comparison
 | expr op=(OR|AND) expr #booleanOperation
 | atom trailer? #atomExpr
 ;

atom
 : constant
 | identifier
 | reference
 | argReplace
 ;

trailer
 : '(' args? ')' trailer?
 | '[' args? ']' trailer?
 | '.' identifier trailer?
 ;

pathname
//@init {_input.enableChannel(1)}
//@after {_input.disableChannel(1)}
 : (identifier ':')? pathElement+
 ;

pathElement
 : identifier
 | NUMBER_LITERAL 
 | BACKSLASH 
 | ';' 
 | '&' 
 | '@' 
 | '+' 
 | '-' 
 | '.' 
 | '[' 
 | ']' 
 | '{' 
 | '}' 
 | '(' 
 | ')' 
 | '!' 
 | '#' 
 | '==' 
 | NOTEQUALS 
 | '%' 
 | '=' 
 | '^' 
 | ',' 
 | '$' 
 | '_'
 ;

specialExpr
 : '(' expr ')'
 | pathname
 | expr
 ;

constant
 : NUMBER_LITERAL #number
 | '.' (T | F | Y | N) '.' #boolean
 | '.' NULL '.' #null
 | (NULLDATE_LITERAL | DATE_LITERAL | TIME_LITERAL | DATETIME_LITERAL) #date
 | STRING_LITERAL #string
 ;

assign
 : STORE expr TO idAttr (',' idAttr)*
 | idAttr '=' expr
 ;

idAttr
 : '.'? identifier trailer?
 ;

twoExpr
 : expr ',' expr
 ;

arrayIndex
 : '(' (expr | twoExpr) ')'
 | '[' (expr | twoExpr) ']'
 ;

datatype
 : CHAR | SHORT | INTEGER | LONG | FLOAT | DOUBLE | STRING
 ;

scopeClause
 : ALL | NEXT NUMBER | RECORD NUMBER | REST
 ;

//identifier
// : TO|DO|IN|IF|AS|ELSE|ON|OFF|ERROR|QUIT|WITH|STORE|PUBLIC|PRIVATE|LOCAL|ARRAY|DELETE|FILE|SET|RELEASE|RECYCLE|CREATE|TABLE|DBF|NAME|FREE|SELECT|USE|READ|EVENTS|CLEAR|CLASS|FORM|LOCATE|FOR|WHILE|NOOPTIMIZE|REPLACE|SHARED|NOWAIT|NOCLEAR|ALL|COUNT|GO|GOTO|TOP|BOTTOM|RECORD|LABEL|MESSAGE|FONT|STYLE|CLOSE|ACTIVATE|AT|UNDEFINE|ALIAS|BY|REPORT|INDEX|VARVFP|VARSCREEN|BELL|CENTURY|CURSOR|DATE|MEMOWIDTH|STATUS|BAR|LIBRARY|NOTIFY|CLOCK|SYSMENU|EXACT|DELETED|PRINTER|NEAR|PROCEDURE|TYPEAHEAD|ORDER|FILTER|CLASSLIB|UNIQUE|CHAR|SHORT|INTEGER|LONG|FLOAT|DOUBLE|STRING|NEXT|NUMBER|REST|REFRESH|T|F|Y|N|ID
// ;

identifier
 : TO|DO|IN|AS|IF|ELIF|ELSE|ENDIF|ON|OFF|ERROR|QUIT|EXIT|WITH|STORE|PUBLIC|PRIVATE|LOCAL|ARRAY|DELETE|FILE|SET|RELEASE|RECYCLE|CREATE|TABLE|DBF|NAME|FREE|SELECT|USE|READ|EVENTS|SHUTDOWN|CLEAR|PROCEDURE|FUNCTION|ENDFUNC|DEFINE|CLASS|ENDDEFINE|LOCATE|FOR|ENDFOR|WHILE|NOOPTIMIZE|STATUS|BAR|MEMOWIDTH|CURSOR|REFRESH|BELL|CENTURY|DATE|ADD|OBJECT|REPLACE|LIBRARY|SHARED|WAIT|WINDOW|NOWAIT|NOCLEAR|NOTIFY|ENDDO|DECLARE|ERASE|INTEGER|SHORT|LONG|DOUBLE|FLOAT|CHAR|STRING|SYSMENU|CLOCK|RETURN|LPARAMETERS|LPARAMETER|PARAMETERS|ALTERNATE|EXACT|ALL|COUNT|GOTO|GO|TOP|BOTTOM|RECORD|CLOSE|APPEND|BLANK|NOMENU|CASE|FROM|REPORT|FORM|NOEJECT|PRINTER|PROMPT|NOCONSOLE|COPY|STRUCTURE|DELETED|SUM|DISTINCT|INTO|NEXT|REST|SKIPKW|EXCLUSIVE|EXCL|NEAR|MKDIR|MD|RMDIR|RD|KEY|KEYBOARD|LABEL|PLAIN|MENU|AT|LINE|SCREEN|NOMARGIN|PAD|OF|COLOR|SCHEME|BEFORE|AFTER|NEGOTIATE|FONT|STYLE|MARK|MESSAGE|ACTIVATE|POPUP|SHADOW|MARGIN|RELATIVE|SELECTION|DEACTIVATE|SAME|NOSHOW|STEP|THEN|UNDEFINE|IFDEF|PUSH|POP|TIMEOUT|ENDWITH|TYPEAHEAD|ALIAS|ORDER|SEEK|WHERE|FILTER|RENAME|INCLUDE|CLASSLIB|BY|UNIQUE|INDEX|TAG|COMPACT|ASCENDING|DESCENDING|CANDIDATE|ADDITIVE|DIMENSION|NOT|AND|OR|SCAN|ENDSCAN|NULL|T|F|Y|N|VARVFP|VARSCREEN|NODEFAULT|DLLS|MACROS|NUMBER|ZAP|ROLLOVER|DEFAULT|SAVE|NOSAVE|ID
 ;

NUMBER_LITERAL : ([0-9]* '.')? [0-9]+ ([Ee] [+\-]? [0-9]+)?
               | [0-9]+ '.'
               | '0' [Xx] [0-9A-Fa-f]*
               ;

NULLDATE_LITERAL : '{' WS+ '/' WS+ '/' WS+ '}';
DATE_LITERAL : '{' [0-9]+ '/' [0-9]+ '/' [0-9]+ '}';
TIME_LITERAL : '{' [0-9]+ ':' [0-9]+ ':' [0-9]+ ( 'AM' | 'PM' )?'}';
DATETIME_LITERAL : '{' [0-9]+ '/' [0-9]+ '/' [0-9]+ WS+ [0-9]+ ':' [0-9]+ ':' [0-9]+ ( 'AM' | 'PM' )?'}';

SEMICOLON: ';';
AMPERSAND: '&';
COMMERCIALAT: '@';
ASTERISK: '*';
PLUS_SIGN: '+';
MINUS_SIGN: '-';
FORWARDSLASH: '/';
PERIOD: '.';
LEFTBRACKET: '[';
RIGHTBRACKET: ']';
LEFTBRACE: '{';
RIGHTBRACE: '}';
LEFTPAREN: '(';
RIGHTPAREN: ')';
BACKSLASH: '\\';
LESSTHAN: '<';
GREATERTHAN: '>';
EXCLAMATION: '!';
HASH: '#';
DOUBLEEQUALS: '==';
NOTEQUALS: ('!='|'<>');
GTEQ: '>=';
LTEQ: '<=';
MODULO: '%';
EQUALS: '=';
CARAT: '^';
COMMA: ',';
DOLLAR: '$';
COLON: ':';
QUESTION: '?';
DOUBLEQUOTE: '"';
SINGLEQUOTE: '\'';

STRING_LITERAL: '\'' ~('\'' | '\n' | '\r')* '\''
              | '"' ~('"' | '\n' | '\r')* '"'
              ;

LINECOMMENT: WS* (('*' | N O T E | '&&') (LINECONT | ~'\n')*)? NL {_tokenStartCharPositionInLine == 0}?;

COMMENT: ('&&' (~'\n')* | ';' WS* '&&' (~'\n')* NL) -> channel(1);

LINECONT : ';' WS* NL -> skip;

TO : T O;
DO : D O;
IN : I N;
AS : A S;
IF : I F;
ELIF : E L I F;
ELSE : E L S E;
ENDIF : E N D I F;
ON : O N;
OFF : O F F;
ERROR : E R R O R;
QUIT : Q U I T;
EXIT : E X I T;
WITH : W I T H;
STORE : S T O R E;
PUBLIC : P U B L I C;
PRIVATE : P R I V A T E;
LOCAL : L O C A L;
ARRAY : A R R A Y;
DELETE : D E L E T E;
FILE : F I L E;
SET : S E T;
RELEASE : R E L E A S E;
RECYCLE : R E C Y C L E;
CREATE : C R E A T E;
TABLE : T A B L E;
DBF : D B F;
NAME : N A M E;
FREE : F R E E;
SELECT : S E L E C T;
USE : U S E;
READ : R E A D;
EVENTS : E V E N T S;
SHUTDOWN : S H U T D O W N;
CLEAR : C L E A R;
PROCEDURE : P R O C E D U R E;
FUNCTION : F U N C T I O N;
ENDPROC : E N D P R O C;
ENDFUNC : E N D F U N C;
DEFINE : D E F I N E;
CLASS : C L A S S;
ENDDEFINE : E N D D E F I N E;
LOCATE : L O C A T E;
FOR : F O R;
ENDFOR : E N D F O R;
WHILE : W H I L E;
NOOPTIMIZE : N O O P T I M I Z E;
STATUS : S T A T U S;
BAR : B A R;
MEMOWIDTH : M E M O W I D T H;
CURSOR : C U R S O R;
REFRESH : R E F R E S H;
BELL : B E L L;
CENTURY : C E N T U R Y;
DATE : D A T E;
ADD : A D D;
OBJECT : O B J E C T;
REPLACE : R E P L A C E;
LIBRARY : L I B R A R Y;
SHARED : S H A R E D;
WAIT : W A I T;
WINDOW : W I N D O W;
NOWAIT : N O W A I T;
NOCLEAR : N O C L E A R;
NOTIFY : N O T I F Y;
ENDDO : E N D D O;
DECLARE : D E C L A R E;
ERASE : E R A S E;
INTEGER : I N T E G E R;
SHORT : S H O R T;
LONG : L O N G;
DOUBLE : D O U B L E;
FLOAT : F L O A T;
CHAR : C H A R;
STRING : S T R I N G;
SYSMENU : S Y S M E N U;
CLOCK : C L O C K;
RETURN : R E T U R N;
LPARAMETERS : L P A R A M E T E R S;
LPARAMETER : L P A R A M E T E R;
PARAMETERS : P A R A M E T E R S;
ALTERNATE : A L T E R N A T E;
EXACT : E X A C T;
ALL : A L L;
COUNT : C O U N T;
GOTO : G O T O;
GO : G O;
TOP : T O P;
BOTTOM : B O T T O M;
RECORD : R E C O R D;
CLOSE : C L O S E;
APPEND : A P P E N D;
BLANK : B L A N K;
NOMENU : N O M E N U;
CASE : C A S E;
ENDCASE : E N D C A S E;
OTHERWISE : O T H E R W I S E;
FROM : F R O M;
REPORT : R E P O R T;
FORM : F O R M;
NOEJECT : N O E J E C T;
PRINTER : P R I N T E R;
PROMPT : P R O M P T;
NOCONSOLE : N O C O N S O L E;
COPY : C O P Y;
STRUCTURE : S T R U C T U R E;
DELETED : D E L E T E D;
SUM : S U M;
DISTINCT : D I S T I N C T;
INTO : I N T O;
NEXT : N E X T;
REST : R E S T;
SKIPKW : S K I P;
EXCLUSIVE : E X C L U S I V E;
EXCL : E X C L;
NEAR : N E A R;
MKDIR : M K D I R;
MD : M D;
RMDIR : R M D I R;
RD : R D;
KEY : K E Y;
KEYBOARD : K E Y B O A R D;
LABEL : L A B E L;
PLAIN : P L A I N;
MENU : M E N U;
AT : A T;
LINE : L I N E;
SCREEN : S C R E E N;
NOMARGIN : N O M A R G I N;
PAD : P A D;
OF : O F;
COLOR : C O L O R;
SCHEME : S C H E M E;
BEFORE : B E F O R E;
AFTER : A F T E R;
NEGOTIATE : N E G O T I A T E;
FONT : F O N T;
STYLE : S T Y L E;
MARK : M A R K;
MESSAGE : M E S S A G E;
ACTIVATE : A C T I V A T E;
POPUP : P O P U P;
SHADOW : S H A D O W;
MARGIN : M A R G I N;
RELATIVE : R E L A T I V E;
SELECTION : S E L E C T I O N;
DEACTIVATE : D E A C T I V A T E;
SAME : S A M E;
NOSHOW : N O S H O W;
STEP : S T E P;
THEN : T H E N;
UNDEFINE : U N D E F (I N E)?;
IFDEF : I F D E F;
PUSH : P U S H;
POP : P O P;
TIMEOUT : T I M E O U T;
ENDWITH : E N D W I T H;
TYPEAHEAD : T Y P E A H E A D;
ALIAS : A L I A S;
ORDER : O R D E R;
SEEK : S E E K;
WHERE : W H E R E;
FILTER : F I L T E R;
RENAME : R E N A M E;
INCLUDE : I N C L U D E;
CLASSLIB : C L A S S L I B;
BY : B Y;
UNIQUE : U N I Q U E;
INDEX : I N D E X;
TAG : T A G;
COMPACT : C O M P A C T;
ASCENDING : A S C E N D I N G;
DESCENDING : D E S C E N D I N G;
CANDIDATE : C A N D I D A T E;
ADDITIVE : A D D I T I V E;
DIMENSION : D I M E N S I O N;
NOT : N O T;
AND : A N D;
OR : O R;
SCAN : S C A N;
ENDSCAN : E N D S C A N;
NULL : N U L L;
T : [Tt];
F : [Ff];
Y : [Yy];
N : [Nn];
VARVFP : '_' V F P;
VARSCREEN : '_' S C R E E N;
NODEFAULT : N O D E F A U L T;
DLLS : D L L S;
MACROS : M A C R O S;
NUMBER : N U M B E R;
ZAP : Z A P;
ROLLOVER : R O L L O V E R;
DEFAULT : D E F A U L T;
SAVE : S A V E;
NOSAVE : N O S A V E;
DATABASES : D A T A B A S E S;
TABLES : T A B L E S;
INDEXES : I N D E X E S;
LOOP: L O O P;


ID : [A-Za-z_] [a-zA-Z0-9_]*;

NL : '\n' | EOF;

WS : [ \t\r] -> channel(1);

UNMATCHED : . ;

fragment A : [Aa];
fragment B : [Bb];
fragment C : [Cc];
fragment D : [Dd];
fragment E : [Ee];
fragment G : [Gg];
fragment H : [Hh];
fragment I : [Ii];
fragment J : [Jj];
fragment K : [Kk];
fragment L : [Ll];
fragment M : [Mm];
fragment O : [Oo];
fragment P : [Pp];
fragment Q : [Qq];
fragment R : [Rr];
fragment S : [Ss];
fragment U : [Uu];
fragment V : [Vv];
fragment W : [Ww];
fragment X : [Xx];
fragment Z : [Zz];