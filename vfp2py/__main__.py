from __future__ import print_function

import sys
import os
import time
import datetime
import re
import tempfile

import argparse

import antlr4

from vfp2py import *

STDLIBS = ['sys', 'os', 'math', 'datetime']

if sys.version_info >= (3,):
    unicode=str

def import_key(module):
    if module in STDLIBS:
        return STDLIBS.index(module)
    else:
        return len(STDLIBS)

class Tic():
    def __init__(self):
        self.start = time.time()

    def tic(self):
        self.start = time.time()

    def toc(self):
        return time.time()-self.start

class CodeStr(str):
    def __repr__(self):
        return self

    def __add__(self, val):
        return CodeStr('{} + {}'.format(self, repr(val)))

class PreprocessVisitor(VisualFoxpro9Visitor):
    def __init__(self):
        self.tokens = None
        self.memory = {}

    def visitPreprocessorCode(self, ctx):
        retval = []
        for child in ctx.getChildren():
            toks = self.visit(child)
            if toks:
                retval += toks
            elif toks is None:
                print('toks was None')
        return retval

    def visitPreprocessorDefine(self, ctx):
        name = ctx.identifier().getText().lower()
        namestart, _ = ctx.identifier().getSourceInterval()
        _, stop = ctx.getSourceInterval()
        tokens = ctx.parser._input.tokens[namestart+1:stop]
        while len(tokens) > 0 and tokens[0].type == ctx.parser.WS:
            tokens.pop(0)
        self.memory[name] = tokens
        return []

    def visitPreprocessorUndefine(self, ctx):
        name = ctx.identifier().getText().lower()
        self.memory.pop(name)
        return []

    def visitPreprocessorInclude(self, ctx):
        visitor = PythonConvertVisitor()
        filename = visitor.visit(ctx.specialExpr())
        if isinstance(filename, CodeStr):
            filename = eval(filename)
        include_visitor = preprocess_file(filename)
        self.memory.update(include_visitor.memory)
        return include_visitor.tokens

    def visitPreprocessorIf(self, ctx):
        if ctx.IF():
            visitor = PythonConvertVisitor()
            ifexpr = eval(repr(visitor.visit(ctx.expr())))
        else:
            name = ctx.identifier().getText().lower()
            ifexpr = name in self.memory
        if ifexpr:
            return self.visit(ctx.ifBody)
        elif ctx.ELSE():
            return self.visit(ctx.elseBody)
        else:
            return []

    def visitNonpreprocessorLine(self, ctx):
        start, stop = ctx.getSourceInterval()
        hidden_tokens = ctx.parser._input.getHiddenTokensToLeft(start)
        retval = []
        process_tokens = (hidden_tokens if hidden_tokens else []) + ctx.parser._input.tokens[start:stop+1]
        hidden_tokens = []
        for tok in process_tokens:
            if tok.text.lower() in self.memory:
                retval += self.memory[tok.text.lower()]
            else:
                if tok.type == ctx.parser.COMMENT:
                    tok.text = '*' + tok.text[2:] + '\n'
                    hidden_tokens.append(tok)
                    continue
                elif tok.type == ctx.parser.LINECOMMENT:
                    if tok.text.strip():
                        tok.text = re.sub(r';[ \t]*\r*\n', '\n', tok.text.strip())
                        lines = tok.text.split('\n')
                        lines = [re.sub(r'^\s*\*?', '*', line) + '\n' for line in lines]
                        tok.text = ''.join(lines)
                retval.append(tok)
        return hidden_tokens + retval

def add_indents(struct, num_indents):
    retval = []
    for item in struct:
        if isinstance(item, list):
            retval.append(add_indents(item, num_indents+1))
        elif item:
            retval.append(' '*4*num_indents + repr(item))
        else:
            retval.append('')
    return '\n'.join(retval)

def get_list(should_be_list):
    try:
        return list(should_be_list)
    except TypeError:
        return [should_be_list]

class PythonConvertVisitor(VisualFoxpro9Visitor):
    def __init__(self):
        super(PythonConvertVisitor, self).__init__()
        self.vfpclassnames = {'custom': 'object',
                              'form': 'vfpfunc.Form',
                              'label': 'vfpfunc.Label',
                              'textbox': 'vfpfunc.Textbox',
                              'checkbox': 'vfpfunc.Checkbox',
                              'spinner': 'vfpfunc.Spinner',
                              'shape': 'vfpfunc.Shape',
                              'commandbutton': 'vfpfunc.CommandButton'
                             }
        self.imports = []
        self.scope = None

    @staticmethod
    def make_func_code(funcname, *kwargs):
        return CodeStr('{}({})'.format(funcname, ', '.join(repr(x) for x in kwargs)))

    @staticmethod
    def to_int(expr):
        if isinstance(expr, float):
            return int(expr)
        else:
            return PythonConvertVisitor.make_func_code('int', expr)

    @staticmethod
    def string_type(val):
        return isinstance(val, (str, unicode)) and not isinstance(val, CodeStr)

    @staticmethod
    def create_string(val):
        try:
            return str(val)
        except UnicodeEncodeError: #can this happen?
            return val

    @staticmethod
    def add_args_to_code(codestr, args):
        return CodeStr(codestr.format(*[repr(arg) for arg in args]))

    def visitPrg(self, ctx):
        self.imports = []
        main = []
        if ctx.line():
            self.scope = {}
            line_structure = []
            for line in get_list(ctx.line()):
                line_structure += self.visit(line)
            if not line_structure:
                line_structure = [CodeStr('pass')]
            main = [CodeStr('def main(argv):'), line_structure, CodeStr(''), CodeStr('if __name__ == \'__main__\':'), [CodeStr('main(sys.argv)')]]
            self.imports.append('sys')
            self.scope = None


        defs = []
        if ctx.classDef():
            for classDef in get_list(ctx.classDef()):
                defs += self.visit(classDef) + [[]]

        if ctx.funcDef():
            for funcDef in get_list(ctx.funcDef()):
                funcname, parameters, funcbody = self.visit(funcDef)
                defs.append(CodeStr('def {}({}):'.format(funcname, ', '.join(parameters))))
                defs += [funcbody] + [[]]

        self.imports = sorted(set(self.imports), key=import_key)
        imports = []
        for n, module in enumerate(self.imports):
            if n != 0 and module not in STDLIBS:
                imports.append('')
            imports.append(module)
        if imports:
            imports.append('')
        return  [CodeStr('import ' + module) if module else '' for module in imports] + defs + main

    def visitLine(self, ctx):
        retval = self.visitChildren(ctx)
        if retval is None:
            print(ctx.getText())
            return []
        if not isinstance(retval, list):
            return [retval]
        return retval

    andfix = re.compile('^&&')
    frontfix = re.compile('^\**')
    endfix = re.compile('\**$')

    def visitLineComment(self, ctx):
        repl = lambda x: '#' * len(x.group())
        comment = ctx.getText().split('\n')[0].strip()
        if len(comment) == 0:
            return ''
        comment = self.andfix.sub('', comment)
        comment = self.frontfix.sub(repl, comment)
        return CodeStr(self.endfix.sub(repl, comment))

    def visitCmdStmt(self, ctx):
        if ctx.cmd():
            return self.visit(ctx.cmd())
        else:
            return self.visit(ctx.setup())

    def visitLines(self, ctx):
        retval = []
        for line in ctx.line():
            retval += self.visit(line)
        def badline(line):
            return line.startswith('#') if hasattr(line, 'startswith') else not line
        if not retval or all(badline(l) for l in retval):
            retval.append(CodeStr('pass'))
        return retval

    def visitClassDef(self, ctx):
        classname, supername = self.visit(ctx.classDefStart())
        retval = [CodeStr('class {}({}):'.format(classname, supername))]
        assignments = []
        funcs = {}
        for stmt in ctx.classDefStmt():
            if isinstance(stmt, VisualFoxpro9Parser.ClassDefAssignContext):
                assignments += self.visit(stmt)
            elif isinstance(stmt, VisualFoxpro9Parser.ClassDefAddObjectContext):
                assignments += self.visit(stmt)
            elif isinstance(stmt, VisualFoxpro9Parser.ClassDefLineCommentContext):
                assignments += [self.visit(stmt)]
            else:
                funcs.update(self.visit(stmt))

        for funcname in funcs:
            parameters, funcbody = funcs[funcname]
            if '.' in funcname:
                newfuncname = funcname.replace('.', '_')
                assignments.append(CodeStr('def {}({}):'.format(newfuncname, ', '.join(parameters))))
                assignments.append(funcbody)
                assignments.append(CodeStr('self.{} = {}'.format(funcname, newfuncname)))

        if '__init__' in funcs:
            funcs['__init__'][1] = [CodeStr('super({}, self).__init__()'.format(classname))] + assignments + funcs['__init__'][1]
        else:
            funcs['__init__'] = [[CodeStr('self')], [CodeStr('super({}, self).__init__()'.format(classname))] + assignments]

        for funcname in funcs:
            parameters, funcbody = funcs[funcname]
            if '.' not in funcname:
                retval.append([CodeStr('def {}({}):'.format(funcname, ', '.join(parameters))), funcbody])

        #retval += ['vfpfunc.classes[%s] = %s' % (repr(classname), classname)]
        return retval

    def visitClassDefStart(self, ctx):
        # DEFINE CLASS identifier (AS identifier)? NL
        #print(ctx.getText())
        names = [self.visit(identifier) for identifier in ctx.identifier()]
        #print(names)
        #exit()
        classname = names[0]
        try:
            supername = names[1]
        except IndexError:
            supername = 'custom'
        if supername in self.vfpclassnames:
            supername = self.vfpclassnames[supername]
        if classname in self.vfpclassnames:
            raise Exception(classname + ' is a reserved classname')
        return classname, supername

    def visitClassDefAssign(self, ctx):
        return [CodeStr('self.' + arg) for arg in self.visit(ctx.assign())]

    def visitClassDefAddObject(self, ctx):
        #ADD OBJECT identifier AS identifier (WITH assignList)? NL
        name = self.visit(ctx.identifier())
        objtype = self.visit(ctx.idAttr()[0])
        if objtype in self.vfpclassnames:
            objtype = self.vfpclassnames[objtype]
        retval = [CodeStr('self.{} = {}({})'.format(name, objtype, ', '.join([self.visit(idAttr) for idAttr, expr in zip(ctx.idAttr()[1:], ctx.expr())])))]
        retval += [CodeStr('self.add_object(self.{})'.format(name))]
        return retval

    def visitClassDefFuncDef(self, ctx):
        funcname, parameters, funcbody = self.visit(ctx.funcDef())
        if funcname == 'init':
            funcname = '__init__'
        return {funcname: [['self'] + parameters, funcbody]}

    def visitFuncDefStart(self, ctx):
#funcDefStart: (PROCEDURE | FUNCTION) idAttr ('(' parameters? ')')? NL parameterDef?;
        return self.visit(ctx.idAttr2()), (self.visit(ctx.parameters()) if ctx.parameters() else []) + (self.visit(ctx.parameterDef()) if ctx.parameterDef() else [])

    def visitParameterDef(self, ctx):
#parameterDef: (LPARAMETER | LPARAMETERS | PARAMETERS) parameters NL;
        return self.visit(ctx.parameters())

    def visitParameter(self, ctx):
#parameter: idAttr (AS idAttr)?;
        return self.visit(ctx.idAttr()[0])

    def visitParameters(self, ctx):
        return [self.visit(parameter) for parameter in ctx.parameter()]

    def visitFuncDef(self, ctx):
#funcDef:  funcDefStart line* funcDefEnd?;
        self.scope = {}
        name, parameters = self.visit(ctx.funcDefStart())
        self.imports.append('vfpfunc')
        body = [CodeStr('vfpfunc.pushscope()')] + self.visit(ctx.lines()) + [CodeStr('vfpfunc.popscope()')]
        self.scope = None
        return name, parameters, body

    def visitPrintStmt(self, ctx):
        return [self.make_func_code('print', *self.visit(ctx.args()))]

    def visitIfStart(self, ctx):
        return self.visit(ctx.expr())

    def visitIfStmt(self, ctx):
        evaluation = self.visit(ctx.ifStart())

        ifBlock = self.visit(ctx.ifBody)
        retval = [CodeStr('if {}:'.format(evaluation)), ifBlock]

        if ctx.elseBody:
            elseBlock = self.visit(ctx.elseBody)
            retval += [CodeStr('else:'), elseBlock]

        return retval

    def visitCaseStmt(self, ctx):
        #doCase caseElement* otherwise? ENDCASE
        n = 0
        retval = []
        for elem in ctx.caseElement():
            if elem.lineComment():
                retval.append(self.visit(elem.lineComment()))
            else:
                expr, lines = self.visit(elem.singleCase())
                if n == 0:
                    retval += [CodeStr('if {}:'.format(expr)), lines]
                else:
                    retval += [CodeStr('elif {}:'.format(expr)), lines]
                n += 1
        if n == 0:
            retval += [CodeStr('if True:'), [CodeStr('pass')]]
        if ctx.otherwise():
            retval += [CodeStr('else:'), self.visit(ctx.otherwise())]
        return retval

    def visitSingleCase(self, ctx):
        #caseExpr line*
        return self.visit(ctx.caseExpr()), self.visit(ctx.lines())

    def visitCaseExpr(self, ctx):
        #CASE expr NL
        return self.visit(ctx.expr())

    def visitOtherwise(self, ctx):
        #OTHERWISE NL line*;
        return self.visit(ctx.lines())

    def visitForStart(self, ctx):
        loopvar = self.visit(ctx.idAttr())
        loop_start = self.to_int(self.visit(ctx.loopStart))
        loop_stop = self.to_int(self.visit(ctx.loopStop)) + 1
        if ctx.loopStep:
            loop_step = self.to_int(self.visit(ctx.loopStep))
            return CodeStr('for {} in range({}, {}, {}):'.format(loopvar, loop_start, loop_stop, loop_step))
        else:
            return CodeStr('for {} in range({}, {}):'.format(loopvar, loop_start, loop_stop))

    def visitForStmt(self, ctx):
        return [self.visit(ctx.forStart()), self.visit(ctx.lines())]

    def visitDeclaration(self, ctx):
        if ctx.PUBLIC():
            string = 'vfp.addpublicvar(\'%s\')'
        if ctx.PRIVATE():
            #string = 'vfp.addprivatevar(\'%s\')'
            savescope = self.scope
            self.scope = None
            names = self.visit(ctx.parameters())
            for name in names:
                savescope[name] = False
            self.scope = savescope
            return '#PRIVATE %s' % ', '.join(names)
        if ctx.LOCAL():
            string = 'vfp.addlocalvar(\'%s\')'
        if ctx.ARRAY():
            string = 'vfp.addarray(\'%s\', %s)'
            values = [self.visit(ctx.arrayIndex())]
            args = [self.visit(ctx.identifier())]
            return [string % (name, value) for name, value in zip(args, values)]
        else:
            return [string % name for name in self.visit(ctx.parameters())]

    def visitAssign(self, ctx):
        if ctx.STORE():
            value = self.visit(ctx.expr())
            args = [self.visit(var) for var in ctx.idAttr()] + [repr(value)]
            return CodeStr(' = '.join(args))
        else:
            name = self.visit(ctx.idAttr()[0])
            value = self.visit(ctx.expr())
            try:
                if value.startswith(name + ' + '):
                    return [CodeStr('{} += {}'.format(name, repr(value[len(name + ' + '):])))]
            except Exception as e:
                pass
            return [CodeStr('{} = {}'.format(name, repr(value)))]

    def visitArgs(self, ctx):
        return [self.visit(c) for c in ctx.expr()]

    def visitComparison(self, ctx):
        symbol_dict = {VisualFoxpro9Lexer.GREATERTHAN: '>',
                       VisualFoxpro9Lexer.GTEQ: '>=',
                       VisualFoxpro9Lexer.LESSTHAN: '<',
                       VisualFoxpro9Lexer.LTEQ: '<=',
                       VisualFoxpro9Lexer.NOTEQUALS: '!=',
                       VisualFoxpro9Lexer.EQUALS: '==',
                       VisualFoxpro9Lexer.DOUBLEEQUALS: '==',
                       VisualFoxpro9Lexer.OR: 'or',
                       VisualFoxpro9Lexer.AND: 'and'
                      }
        left = self.visit(ctx.expr(0))
        right = self.visit(ctx.expr(1))
        if isinstance(right, float) and right == int(right):
            right = int(right)
        symbol = symbol_dict[ctx.op.type]
        return CodeStr('{} {} {}'.format(repr(left), symbol, repr(right)))

    def scopeId(self, text, vartype):
        if '.' in text:
            vals = text.split('.')
        else:
            vals = [text]
        if self.scope is not None:
            t = vals[0]
            n1 = t.find('[')
            n2 = t.find('(')
            if n2 > n1:
                r = t[n1:]
                t = t[:n1]
            elif n1 > n2:
                r = t[n1:]
                t = t[:n1]
            else:
                r = ''
            if t not in self.scope:
                self.imports.append('vfpfunc')
                #vals[0] = 'vfpfunc.' + vartype + '[' + repr(str(t)) + ']' + r
        text = '.'.join(vals)
        return CodeStr(text)

    def createIdAttr(self, identifier, trailer):
        identifier = self.scopeId(identifier, 'val')
        if identifier == 'this':
            identifier = CodeStr('self')
        if identifier == 'thisform':
            identifier = CodeStr('self.parentform')
        if trailer and len(trailer) == 1 and isinstance(trailer[0], list):
            args = trailer[0]
            return self.visitFuncCall(identifier, args)
        if trailer:
            trailer = self.convert_trailer_args(trailer)
        else:
            trailer = CodeStr('')
        return CodeStr('{}{}'.format(repr(identifier), repr(trailer)))

    def convert_trailer_args(self, trailers):
        retval = ''
        for trailer in trailers:
            if isinstance(trailer, list):
                retval += '({})'.format(', '.join(repr(t) for t in trailer))
            else:
                retval += '.' + trailer
        return CodeStr(retval)

    def visitTrailer(self, ctx):
        trailer = self.visit(ctx.trailer()) if ctx.trailer() else []
        if ctx.args():
            retval = [[x for x in self.visit(ctx.args())]]
        elif ctx.identifier():
            retval = [self.visit(ctx.identifier())]
        else:
            retval = [[]]
        return retval + trailer

    def visitIdAttr(self, ctx):
        identifier = self.visit(ctx.identifier())
        trailer = self.visit(ctx.trailer()) if ctx.trailer() else None
        return self.createIdAttr(identifier, trailer)

    def visitIdAttr2(self, ctx):
        return '.'.join(self.visit(identifier) for identifier in ctx.identifier())

    def visitAtomExpr(self, ctx):
        atom = self.visit(ctx.atom())
        trailer = self.visit(ctx.trailer()) if ctx.trailer() else None
        if isinstance(ctx.atom().getChild(0), VisualFoxpro9Parser.IdentifierContext):
            return self.createIdAttr(atom, trailer)
        elif trailer:
            for i, t in enumerate(trailer):
                if isinstance(t, list):
                    trailer[i] = self.add_args_to_code('({})', t)
                else:
                    trailer[i] = '.' + trailer[i]
            return CodeStr(''.join([repr(self.visit(ctx.atom()))] + trailer))
        else:
            return self.visit(ctx.atom())

    def visitIdList(self, ctx):
        return [self.visit(i) for i in get_list(ctx.idAttr())]

    def visitFuncCall(self, funcname, args):
        if funcname == 'chr' and len(args) == 1 and isinstance(args[0], float):
            return chr(int(args[0]))
        if funcname == 'space' and len(args) == 1 and isinstance(args[0], float):
            return ' '*int(args[0])
        if funcname == 'date' and len(args) == 0:
            self.imports.append('datetime')
            return self.make_func_code('datetime.datetime.now().date')
        if funcname == 'iif' and len(args) == 3:
            return self.add_args_to_code('({} if {} else {})', [args[i] for i in (1, 0, 2)])
        if funcname == 'alltrim' and len(args) == 1:
            return self.add_args_to_code('{}.strip()', args)
        if funcname == 'strtran' and len(args) == 3:
            return self.make_func_code('{}.replace'.format(args[0]), *args[1:])
        if funcname == 'left' and len(args) == 2:
            args[1] = self.to_int(args[1])
            return self.add_args_to_code('{}[:{}]', args)
        if funcname == 'ceiling' and len(args) == 1:
            self.imports.append('math')
            return self.make_func_code('math.ceil', *args)
        if funcname == 'str':
            self.imports.append('vfpfunc')
            return self.make_func_code('vfpfunc.num_to_str', *args)
        if funcname == 'file':
            self.imports.append('os')
            return self.make_func_code('os.path.isfile', *args)
        if funcname == 'used':
            self.imports.append('vfpfunc')
            return self.make_func_code('vfpfunc.used', *args)
        if funcname == 'round':
            return self.make_func_code(funcname, *args)
        if funcname in dir(vfpfunc):
            self.imports.append('vfpfunc')
            funcname = 'vfpfunc.' + funcname
        else:
            funcname = self.scopeId(funcname, 'func')
        return self.make_func_code(funcname, *args)

    #(MD | MKDIR | RD | RMDIR) specialExpr #Directory
    def visitAddRemoveDirectory(self, ctx):
        self.imports.append('os')
        if ctx.MD() or ctx.MKDIR():
            funcname = 'mkdir'
        if ctx.RD() or ctx.RMDIR():
            funcname = 'rmdir'
        return self.make_func_code('os.' + funcname, self.visit(ctx.specialExpr()))

    #specialExpr: pathname | expr;
    def visitSpecialExpr(self, ctx):
        if ctx.constant():
            return self.visit(ctx.constant())
        elif ctx.pathname():
            return self.visit(ctx.pathname())
        elif ctx.expr():
            return self.visit(ctx.expr())

    def visitPathname(self, ctx):
        return self.create_string(ctx.getText())

    def visitNumber(self, ctx):
        num = ctx.NUMBER_LITERAL().getText()
        if num[-1:].lower() == 'e':
            num += '0'
        return float(num)

    def visitBoolean(self, ctx):
        if ctx.T():
            return True
        if ctx.Y():
            return True
        if ctx.F():
            return False
        if ctx.N():
            return False
        raise Exception('Can\'t convert boolean:' + ctx.getText())

    def visitNull(self, ctx):
        return None

    def visitDate(self, ctx):
        if ctx.NULLDATE_LITERAL():
            return None
        raise Exception('Date constants not implemented for none null dates')
        innerstr = ctx.getText()[1:-1]
        if ctx.DATE_LITERAL():
            m, d, y = innerstr.split('/')
            if len(y) == 2:
                y = '19'+y
            if len(y) != 4:
                raise Exception('year must be 2 or 4 digits in date constant: ' + ctx.getText())
            try:
                return datetime.date(int(y), int(m), int(d))
            except ValueError as e:
                raise Exception('invalid date constant: ' + ctx.getText())
        #if ctx.TIME_LITERAL():
        #    hour, minute, second
        #    if innerstr[-2:].upper() in ('AM', 'PM'):
        #
        return datetime.dateime(1, 1, 1, 0, 0, 0)

    def visitString(self, ctx):
        return self.create_string(ctx.getText()[1:-1])

    # expr op=('**'|'^') expr */
    def visitPower(self, ctx):
        return self.operationExpr(ctx, '**')

    # expr op=('*'|'/') expr */
    def visitMultiplication(self, ctx):
        return self.operationExpr(ctx, ctx.op.type)

    # expr op=('+'|'-') expr */
    def visitAddition(self, ctx):
        return self.operationExpr(ctx, ctx.op.type)

    # expr '%' expr #Mod
    def visitMod(self, ctx):
        return self.operationExpr(ctx, '%')

    def operationExpr(self, ctx, operation):
        left = self.visit(ctx.expr(0))  # get value of left subexpression
        right = self.visit(ctx.expr(1)) # get value of right subexpression
        symbols = {
            '**': '**',
            '%': '%',
            VisualFoxpro9Parser.ASTERISK: '*',
            VisualFoxpro9Parser.FORWARDSLASH: '/',
            VisualFoxpro9Parser.PLUS_SIGN: '+',
            VisualFoxpro9Parser.MINUS_SIGN: '-'
        }
        if self.string_type(left) and self.string_type(right) and operation == VisualFoxpro9Parser.PLUS_SIGN:
            return left + right
        return CodeStr('({} {} {})'.format(repr(left), symbols[operation], repr(right)))

    def visitSubExpr(self, ctx):
        return CodeStr('({})'.format(self.visit(ctx.expr())))

    def visitDoFunc(self, ctx):
        func = self.visit(ctx.idAttr())
        if ctx.args():
            args = self.visit(ctx.args())
        else:
            args = []
        namespace = self.visit(ctx.specialExpr())
        if namespace:
            if namespace.endswith('.app'):
                namespace = namespace[:-4]
            func = namespace + '.' + func
        return self.make_func_code(func, *args)

    def visitMethodCall(self, ctx):
        return self.visit(ctx.idAttr()) + '.' + self.visit(ctx.identifier()) + '()'

    def visitClearStmt(self, ctx):
        if ctx.ALL:
            return 'vfpfunc.clearall()'
        if ctx.DLLS:
            return 'vfpfunc.cleardlls(' + self.visit(ctx.args()) + ')'
        if ctx.MACROS:
            return 'vfpfunc.clearmacros()'
        if ctx.EVENTS:
            return 'vfpfunc.clearevents()'

    def visitOnError(self, ctx):
        if ctx.cmd():
            func = self.visit(ctx.cmd())
        else:
            return ['vfp.error_func = None']
        return ['vfp.error_func = lambda: ' + func]

    def visitIdentifier(self, ctx):
        return CodeStr(ctx.getText().lower())

    def visitArrayIndex(self, ctx):
        if ctx.twoExpr():
            return self.visit(ctx.twoExpr())
        else:
            return self.visit(ctx.expr())

    def visitTwoExpr(self, ctx):
        return [self.visit(expr) for expr in ctx.expr()]

    def visitQuit(self, ctx):
        return [CodeStr('vfp.quit()')]

    def visitDeleteFile(self, ctx):
        if ctx.specialExpr():
            filename = self.visit(ctx.specialExpr())
        else:
            filename = None
        if ctx.RECYCLE():
            return self.make_func_code('vfp.delete_file', filename, True)
        else:
            self.imports.append('os')
            return self.make_func_code('os.remove', filename)

    def visitFile(self, ctx):
        return ctx.getText()

    def visitRelease(self, ctx):
        #RELEASE vartype=(PROCEDURE|CLASSLIB)? args #release
        if ctx.ALL():
            return self.make_funce_code('vfp.release', '')
        savescope = self.scope
        self.scope = None
        retval = [self.make_func_code('vfp.release', arg) for arg in self.visit(ctx.args())]
        self.scope = savescope
        return retval

    def visitWaitCmd(self, ctx):
        #WAIT (TO toExpr=expr | WINDOW (AT atExpr1=expr ',' atExpr2=expr)? | NOWAIT | CLEAR | NOCLEAR | TIMEOUT timeout=expr | message=expr)*
        message = repr(self.visit(ctx.message) if ctx.message else '')
        to_expr = repr(self.visit(ctx.toExpr) if ctx.TO() else None)
        if ctx.WINDOW():
            if ctx.AT():
                window=[self.visit(ctx.atExpr1), self.visit(ctx.atExpr2)]
            else:
                window = [-1, -1]
        else:
            window = []
        window = repr(window)
        nowait = repr(ctx.NOWAIT() != None)
        noclear = repr(ctx.NOCLEAR() != None)
        timeout = repr(self.visit(ctx.timeout)) if ctx.TIMEOUT() else -1
        code = 'vfpfunc.wait({}, to={}, window={}, nowait={}, noclear={}, timeout={})'
        return CodeStr(code.format(message, to_expr, window, nowait, noclear, timeout))

    def visitCreateTable(self, ctx):
        if ctx.TABLE():
            func = 'vfpfunc.db.create_table'
        elif ctx.DBF():
            func = 'vfpfunc.db.create_dbf'
        tablename = self.visit(ctx.specialExpr())
        tablesetup = zip(ctx.identifier()[::2], ctx.identifier()[1::2], ctx.arrayIndex())
        tablesetup = ((self.visit(id1), self.visit(id2), self.visit(size)) for id1, id2, size in tablesetup)
        setupstring = '; '.join('{} {}({})'.format(id1, id2, int(float(size))) for id1, id2, size in tablesetup)
        free = 'free' if ctx.FREE() else ''
        return self.make_func_code(func, tablename, setupstring, free)

    def visitSelect(self, ctx):
        if ctx.tablename:
            return self.make_func_code('vfpfunc.db.select', self.visit(ctx.tablename))
        #NEED TO ADD - SQL SELECT

    def visitGoRecord(self, ctx):
        if ctx.TOP():
            record = 0
        elif ctx.BOTTOM():
            record = -1
        else:
            record = self.visit(ctx.expr())
        if ctx.idAttr():
            name = self.visit(ctx.idAttr)
        else:
            name = None
        return self.make_func_code('vfpfunc.db.goto', name, record)

    def visitUse(self, ctx):
        shared = ctx.SHARED()
        exclusive = ctx.EXCL() or ctx.EXCLUSIVE()
        if shared and exclusive:
            raise Exception('cannot combine shared and exclusive')
        elif shared:
            opentype = 'shared'
        elif exclusive:
            opentype = 'exclusive'
        else:
            opentype = None
        if ctx.name:
            name = self.visit(ctx.name)
        else:
            name = None
        if ctx.workArea:
            workarea = self.visit(ctx.workArea)
            if isinstance(workarea, float):
                workarea = int(workarea)
        else:
            workarea = None
        return self.make_func_code('vfpfunc.db.use', name, workarea, opentype)

    def visitAppend(self, ctx):
        if ctx.FROM():
            pass #NEED TO ADD - APPEND FROM
        else:
            menupopup = not ctx.BLANK()
            if ctx.IN():
                tablename = self.visit(ctx.idAttr())
            else:
                tablename = None
            return self.make_func_code('vfpfunc.db.append', tablename, menupopup)

    def visitReplace(self, ctx):
        value = self.visit(ctx.expr(0))
        if ctx.scopeClause():
            scope = self.visit(ctx.scopeClause())
        else:
            scope = None
        field = self.visit(ctx.idAttr()).split('.')
        if len(field) > 1:
            table = '.'.join(field[:-1])
            field = str(field[-1])
        else:
            field = field[0]
            table = None
        return self.make_func_code('vfpfunc.db.replace', table, field, value, scope)

    def visitReport(self, ctx):
        if ctx.specialExpr():
            formname = self.visit(ctx.specialExpr())
        else:
            formname = None
        return self.make_func_code('vfpfunc.report_form', formname)

    def visitSetCmd(self, ctx):
        if ctx.setword.text.lower() == 'printer':
            args=['printer']
            if ctx.ON():
                args.append(1)
                if ctx.PROMPT():
                    args.append(True)
            elif ctx.OFF():
                args.append(0)
            elif ctx.TO():
                if ctx.DEFAULT():
                    args.append(['Default', None])
                elif ctx.NAME():
                    args.append(['Name', self.visit(ctx.specialExpr()[0])])
                elif ctx.specialExpr():
                    args.append(['File', self.visit(ctx.specialExpr()[0])])
                    args.append(ctx.ADDITIVE() != None)
            return self.make_func_code('vfpfunc.set', *args)

    def visitReturnStmt(self, ctx):
        args = []
        if ctx.expr():
            args.append(self.visit(ctx.expr()))
        return self.add_args_to_code('return {}', args)

def print_tokens(stream):
    stream.fill()
    for t in stream.tokens:
        if t.channel != 0:
            continue
        #if token.type == VisualFoxpro9Lexer.WS or (token.type > 0 and token.channel==0):
        #    print(token.text, end='')
        out = (t.tokenIndex, t.start, t.stop, repr(str(t.text)), t.type, t.line, t.column, t.channel)
        print('[@%d,%d:%d=%s,<%d>,%d:%d,%d]' % out)
    stream.reset()

def convert(codestr):
    input_stream = antlr4.InputStream(codestr)
    lexer = VisualFoxpro9Lexer(input_stream)
    stream = antlr4.CommonTokenStream(lexer)
    parser = VisualFoxpro9Parser(stream)
    tree = parser.expr()
    visitor = PythonConvertVisitor()
    return visitor.visit(tree)

def evaluateCode(codestr):
    return eval(convert(codestr))

def preprocess_file(filename):
    import codecs
    fid = codecs.open(filename, 'r', 'ISO-8859-1')
    data = fid.read()
    fid.close()

    input_stream = antlr4.InputStream(data)
    lexer = VisualFoxpro9Lexer(input_stream)
    stream = MultichannelTokenStream(lexer)
    #print_tokens(stream)
    #exit()
    parser = VisualFoxpro9Parser(stream)
    tree = parser.preprocessorCode()
    visitor = PreprocessVisitor()
    visitor.tokens = visitor.visit(tree)
    return visitor

class MultichannelTokenStream(antlr4.CommonTokenStream):
    def __init__(self, lexer, channel=antlr4.Token.DEFAULT_CHANNEL):
        super(MultichannelTokenStream, self).__init__(lexer)
        self.channels = [channel]

    def nextTokenOnChannel(self, i, channel):
        self.sync(i)
        if i>=len(self.tokens):
            return -1
        token = self.tokens[i]
        while token.channel not in self.channels:
            if token.type==antlr4.Token.EOF:
                return -1
            i += 1
            self.sync(i)
            token = self.tokens[i]
        return i

    def previousTokenOnChannel(self, i, channel):
        while i>=0 and self.tokens[i].channel not in self.channels:
            i -= 1
        return i

    def enableChannel(self, channel):
        if channel not in self.channels:
            self.channels.append(channel)
            self.channels = sorted(self.channels)
            #print('added channel %s: %s' % (repr(channel), repr(self.channels)))

    def disableChannel(self, channel):
        if channel in self.channels:
            self.channels.remove(channel)
            #print('removed channel %s: %s' % (repr(channel), repr(self.channels)))

class just_raise_an_error:
    def __init__(self):
        pass

    @staticmethod
    def reportAttemptingFullContext(ctx, arg2, arg3, arg4, arg5, arg6):
        pass#raise Exception('error')

    @staticmethod
    def reportAmbiguity(ctx, arg2, arg3, arg4, arg5, arg6, arg7):
        pass#raise Exception('error')

    @staticmethod
    def reportContextSensitivity(ctx, arg2, arg3, arg4, arg5, arg6):
        pass#raise Exception('error')

    @staticmethod
    def syntaxError(ctx, arg2, arg3, arg4, arg5, arg6):
        raise Exception('error')

def time_lines(data):
    testdata = data.split('\n')
    if not testdata[-1]:
        testdata.pop()
    retval = []
    input_string = ''
    while testdata:
        input_string += testdata.pop(0) + '\n'
        try:
            #print('trying: %s' % repr(input_string)[:50] + '... ' + repr(input_string)[-50:] )
            input_stream = antlr4.InputStream(input_string)
            lexer = VisualFoxpro9Lexer(input_stream)
            stream = MultichannelTokenStream(lexer)
            #print_tokens(stream)
            parser = VisualFoxpro9Parser(stream)
            parser.removeErrorListeners()
            parser.addErrorListener(just_raise_an_error)
            tic = Tic()
            tree = parser.prg()
            retval.append([tic.toc(), input_string])
            input_string = ''
        except Exception as e:
            pass
    return retval

def main(argv):
    tic = Tic()
    tokens = preprocess_file(argv[1]).tokens
    print(tic.toc())
    tic.tic()
    data = ''.join(token.text.replace('\r', '') for token in tokens)
    with tempfile.NamedTemporaryFile() as fid:
        pass
    with open(fid.name, 'wb') as fid:
        fid.write(data.encode('utf-8'))
    input_stream = antlr4.InputStream(data)
    lexer = VisualFoxpro9Lexer(input_stream)
    stream = MultichannelTokenStream(lexer)
    #print_tokens(stream)
    parser = VisualFoxpro9Parser(stream)
    print(tic.toc())
    tic.tic()
    tree = parser.prg()
    print(tic.toc())
    #timed_lines = time_lines(data)
    #print(sum(item[0] for item in timed_lines))
    #for item in time_lines(data):
    #    print(item[0])
    #    print(add_indents([item[1]], 0))
    visitor = PythonConvertVisitor()
    output_tree = visitor.visit(tree)
    output = add_indents(output_tree, 0)
    output = re.sub(r'\'\s*\+\s*\'', '', output)
    with open(argv[2], 'wb') as fid:
        fid.write(output)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
