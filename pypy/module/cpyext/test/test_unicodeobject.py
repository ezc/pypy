# encoding: iso-8859-15
from pypy.module.cpyext.test.test_api import BaseApiTest
from pypy.module.cpyext.test.test_cpyext import AppTestCpythonExtensionBase
from pypy.module.cpyext.unicodeobject import (
    Py_UNICODE, PyUnicodeObject, new_empty_unicode)
from pypy.module.cpyext.api import PyObjectP, PyObject, Py_CLEANUP_SUPPORTED
from pypy.module.cpyext.pyobject import Py_DecRef, from_ref
from rpython.rtyper.lltypesystem import rffi, lltype
import sys, py

class AppTestUnicodeObject(AppTestCpythonExtensionBase):
    def test_unicodeobject(self):
        module = self.import_extension('foo', [
            ("get_hello1", "METH_NOARGS",
             """
                 return PyUnicode_FromStringAndSize(
                     "Hello world<should not be included>", 11);
             """),
            ("test_GetSize", "METH_NOARGS",
             """
                 PyObject* s = PyUnicode_FromString("Hello world");
                 int result = 0;

                 if(PyUnicode_GetSize(s) == 11) {
                     result = 1;
                 }
                 if(s->ob_type->tp_basicsize != sizeof(void*)*5)
                     result = 0;
                 Py_DECREF(s);
                 return PyBool_FromLong(result);
             """),
            ("test_GetSize_exception", "METH_NOARGS",
             """
                 PyObject* f = PyFloat_FromDouble(1.0);
                 Py_ssize_t size = PyUnicode_GetSize(f);

                 Py_DECREF(f);
                 return NULL;
             """),
             ("test_is_unicode", "METH_VARARGS",
             """
                return PyBool_FromLong(PyUnicode_Check(PyTuple_GetItem(args, 0)));
             """)])
        assert module.get_hello1() == 'Hello world'
        assert module.test_GetSize()
        raises(TypeError, module.test_GetSize_exception)

        assert module.test_is_unicode("")
        assert not module.test_is_unicode(())

    def test_unicode_buffer_init(self):
        module = self.import_extension('foo', [
            ("getunicode", "METH_NOARGS",
             """
                 PyObject *s, *t;
                 Py_UNICODE* c;
                 Py_ssize_t len;

                 s = PyUnicode_FromUnicode(NULL, 4);
                 if (s == NULL)
                    return NULL;
                 t = PyUnicode_FromUnicode(NULL, 3);
                 if (t == NULL)
                    return NULL;
                 Py_DECREF(t);
                 c = PyUnicode_AsUnicode(s);
                 c[0] = 'a';
                 c[1] = 0xe9;
                 c[3] = 'c';
                 return s;
             """),
            ])
        s = module.getunicode()
        assert len(s) == 4
        assert s == 'a\xe9\x00c'

    def test_format_v(self):
        module = self.import_extension('foo', [
            ("test_unicode_format_v", "METH_VARARGS",
             '''
                 return helper("bla %d ble %s\\n",
                        PyLong_AsLong(PyTuple_GetItem(args, 0)),
                        _PyUnicode_AsString(PyTuple_GetItem(args, 1)));
             '''
             )
            ], prologue='''
            PyObject* helper(char* fmt, ...)
            {
              va_list va;
              PyObject* res;
              va_start(va, fmt);
              res = PyUnicode_FromFormatV(fmt, va);
              va_end(va);
              return res;
            }
            ''')
        res = module.test_unicode_format_v(1, "xyz")
        assert res == "bla 1 ble xyz\n"

    def test_format(self):
        module = self.import_extension('foo', [
            ("test_unicode_format", "METH_VARARGS",
             '''
                 return PyUnicode_FromFormat("bla %d ble %s\\n",
                        PyLong_AsLong(PyTuple_GetItem(args, 0)),
                        _PyUnicode_AsString(PyTuple_GetItem(args, 1)));
             '''
             )
            ])
        res = module.test_unicode_format(1, "xyz")
        assert res == "bla 1 ble xyz\n"

    def test_aswidecharstring(self):
        module = self.import_extension('foo', [
            ("aswidecharstring", "METH_O",
             '''
             PyObject *result;
             Py_ssize_t size;
             wchar_t *buffer;

             buffer = PyUnicode_AsWideCharString(args, &size);
             if (buffer == NULL)
                 return NULL;

             result = PyUnicode_FromWideChar(buffer, size + 1);
             PyMem_Free(buffer);
             if (result == NULL)
                 return NULL;
             return Py_BuildValue("(Nn)", result, size);
             ''')])
        res = module.aswidecharstring("Caf\xe9")
        assert res == ("Caf\xe9\0", 4)

    def test_CompareWithASCIIString(self):
        module = self.import_extension('foo', [
            ("compare", "METH_VARARGS",
             '''
             PyObject *uni;
             const char* s;
             int res;

             if (!PyArg_ParseTuple(args, "Uy", &uni, &s))
                 return NULL;

             res = PyUnicode_CompareWithASCIIString(uni, s);
             return PyLong_FromLong(res);
             ''')])
        assert module.compare("abc", b"abc") == 0
        assert module.compare("abd", b"abc") == 1
        assert module.compare("abb", b"abc") == -1
        assert module.compare("caf\xe9", b"caf\xe9") == 0
        assert module.compare("abc", b"ab") == 1
        assert module.compare("ab\0", b"ab") == 1
        assert module.compare("ab", b"abc") == -1
        assert module.compare("", b"abc") == -1
        assert module.compare("abc", b"") == 1


class TestUnicode(BaseApiTest):
    def test_unicodeobject(self, space, api):
        assert api.PyUnicode_GET_SIZE(space.wrap(u'sp�m')) == 4
        assert api.PyUnicode_GetSize(space.wrap(u'sp�m')) == 4
        unichar = rffi.sizeof(Py_UNICODE)
        assert api.PyUnicode_GET_DATA_SIZE(space.wrap(u'sp�m')) == 4 * unichar

        encoding = rffi.charp2str(api.PyUnicode_GetDefaultEncoding())
        w_default_encoding = space.call_function(
            space.sys.get('getdefaultencoding')
        )
        assert encoding == space.unwrap(w_default_encoding)

    def test_AS(self, space, api):
        word = space.wrap(u'spam')
        array = rffi.cast(rffi.CWCHARP, api.PyUnicode_AS_DATA(word))
        array2 = api.PyUnicode_AS_UNICODE(word)
        array3 = api.PyUnicode_AsUnicode(word)
        for (i, char) in enumerate(space.unwrap(word)):
            assert array[i] == char
            assert array2[i] == char
            assert array3[i] == char
        self.raises(space, api, TypeError, api.PyUnicode_AsUnicode,
                    space.wrapbytes('spam'))

        utf_8 = rffi.str2charp('utf-8')
        encoded = api.PyUnicode_AsEncodedString(space.wrap(u'sp�m'),
                                                utf_8, None)
        assert space.unwrap(encoded) == 'sp\xc3\xa4m'
        encoded_obj = api.PyUnicode_AsEncodedObject(space.wrap(u'sp�m'),
                                                utf_8, None)
        assert space.eq_w(encoded, encoded_obj)
        self.raises(space, api, TypeError, api.PyUnicode_AsEncodedString,
               space.newtuple([1, 2, 3]), None, None)
        self.raises(space, api, TypeError, api.PyUnicode_AsEncodedString,
               space.wrapbytes(''), None, None)
        ascii = rffi.str2charp('ascii')
        replace = rffi.str2charp('replace')
        encoded = api.PyUnicode_AsEncodedString(space.wrap(u'sp�m'),
                                                ascii, replace)
        assert space.unwrap(encoded) == 'sp?m'
        rffi.free_charp(utf_8)
        rffi.free_charp(replace)
        rffi.free_charp(ascii)

        buf = rffi.unicode2wcharp(u"12345")
        api.PyUnicode_AsWideChar(space.wrap(u'longword'), buf, 5)
        assert rffi.wcharp2unicode(buf) == 'longw'
        api.PyUnicode_AsWideChar(space.wrap(u'a'), buf, 5)
        assert rffi.wcharp2unicode(buf) == 'a'
        rffi.free_wcharp(buf)

    def test_fromstring(self, space, api):
        s = rffi.str2charp(u'sp�m'.encode("utf-8"))
        w_res = api.PyUnicode_FromString(s)
        assert space.unwrap(w_res) == u'sp�m'

        res = api.PyUnicode_FromStringAndSize(s, 4)
        w_res = from_ref(space, res)
        api.Py_DecRef(res)
        assert space.unwrap(w_res) == u'sp�'
        rffi.free_charp(s)

    def test_unicode_resize(self, space, api):
        py_uni = new_empty_unicode(space, 10)
        ar = lltype.malloc(PyObjectP.TO, 1, flavor='raw')
        py_uni.c_buffer[0] = u'a'
        py_uni.c_buffer[1] = u'b'
        py_uni.c_buffer[2] = u'c'
        ar[0] = rffi.cast(PyObject, py_uni)
        api.PyUnicode_Resize(ar, 3)
        py_uni = rffi.cast(PyUnicodeObject, ar[0])
        assert py_uni.c_size == 3
        assert py_uni.c_buffer[1] == u'b'
        assert py_uni.c_buffer[3] == u'\x00'
        # the same for growing
        ar[0] = rffi.cast(PyObject, py_uni)
        api.PyUnicode_Resize(ar, 10)
        py_uni = rffi.cast(PyUnicodeObject, ar[0])
        assert py_uni.c_size == 10
        assert py_uni.c_buffer[1] == 'b'
        assert py_uni.c_buffer[10] == '\x00'
        Py_DecRef(space, ar[0])
        lltype.free(ar, flavor='raw')

    def test_AsUTF8String(self, space, api):
        w_u = space.wrap(u'sp�m')
        w_res = api.PyUnicode_AsUTF8String(w_u)
        assert space.type(w_res) is space.w_str
        assert space.unwrap(w_res) == 'sp\xc3\xa4m'
    
    def test_decode_utf8(self, space, api):
        u = rffi.str2charp(u'sp�m'.encode("utf-8"))
        w_u = api.PyUnicode_DecodeUTF8(u, 5, None)
        assert space.type(w_u) is space.w_unicode
        assert space.unwrap(w_u) == u'sp�m'
        
        w_u = api.PyUnicode_DecodeUTF8(u, 2, None)
        assert space.type(w_u) is space.w_unicode
        assert space.unwrap(w_u) == 'sp'
        rffi.free_charp(u)

    def test_encode_utf8(self, space, api):
        u = rffi.unicode2wcharp(u'sp�m')
        w_s = api.PyUnicode_EncodeUTF8(u, 4, None)
        assert space.unwrap(w_s) == u'sp�m'.encode('utf-8')
        rffi.free_wcharp(u)

    def test_encode_decimal(self, space, api):
        with rffi.scoped_unicode2wcharp(u' (12, 35 ABC)') as u:
            with rffi.scoped_alloc_buffer(20) as buf:
                res = api.PyUnicode_EncodeDecimal(u, 13, buf.raw, None)
                s = rffi.charp2str(buf.raw)
        assert res == 0
        assert s == ' (12, 35 ABC)'

        with rffi.scoped_unicode2wcharp(u' (12, \u1234\u1235)') as u:
            with rffi.scoped_alloc_buffer(20) as buf:
                res = api.PyUnicode_EncodeDecimal(u, 9, buf.raw, None)
        assert res == -1
        api.PyErr_Clear()

        with rffi.scoped_unicode2wcharp(u' (12, \u1234\u1235)') as u:
            with rffi.scoped_alloc_buffer(20) as buf:
                with rffi.scoped_str2charp("replace") as errors:
                    res = api.PyUnicode_EncodeDecimal(u, 9, buf.raw,
                                                      errors)
                s = rffi.charp2str(buf.raw)
        assert res == 0
        assert s == " (12, ??)"

        with rffi.scoped_unicode2wcharp(u'12\u1234') as u:
            with rffi.scoped_alloc_buffer(20) as buf:
                with rffi.scoped_str2charp("xmlcharrefreplace") as errors:
                    res = api.PyUnicode_EncodeDecimal(u, 3, buf.raw,
                                                      errors)
                s = rffi.charp2str(buf.raw)
        assert res == 0
        assert s == "12&#4660;"

    def test_encode_fsdefault(self, space, api):
        w_u = space.wrap(u'sp�m')
        w_s = api.PyUnicode_EncodeFSDefault(w_u)
        with rffi.scoped_str2charp(space.str_w(w_s)) as encoded:
            w_decoded = api.PyUnicode_DecodeFSDefaultAndSize(encoded, space.len_w(w_s))
            assert space.eq_w(w_decoded, w_u)
            w_decoded = api.PyUnicode_DecodeFSDefault(encoded)
            assert space.eq_w(w_decoded, w_u)

    def test_fsconverter(self, space, api):
        # Input is bytes
        w_input = space.wrapbytes("test")
        with lltype.scoped_alloc(PyObjectP.TO, 1) as result:
            # Decoder
            ret = api.PyUnicode_FSDecoder(w_input, result)
            assert ret == Py_CLEANUP_SUPPORTED
            assert space.isinstance_w(from_ref(space, result[0]), space.w_unicode)
            assert api.PyUnicode_FSDecoder(None, result) == 1
            # Converter
            ret = api.PyUnicode_FSConverter(w_input, result)
            assert ret == Py_CLEANUP_SUPPORTED
            assert space.eq_w(from_ref(space, result[0]), w_input)
            assert api.PyUnicode_FSDecoder(None, result) == 1
        # Input is unicode
        w_input = space.wrap("test")
        with lltype.scoped_alloc(PyObjectP.TO, 1) as result:
            # Decoder
            ret = api.PyUnicode_FSDecoder(w_input, result)
            assert ret == Py_CLEANUP_SUPPORTED
            assert space.eq_w(from_ref(space, result[0]), w_input)
            assert api.PyUnicode_FSDecoder(None, result) == 1
            # Converter
            ret = api.PyUnicode_FSConverter(w_input, result)
            assert ret == Py_CLEANUP_SUPPORTED
            assert space.isinstance_w(from_ref(space, result[0]), space.w_bytes)
            assert api.PyUnicode_FSDecoder(None, result) == 1

    def test_IS(self, space, api):
        for char in [0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f,
                     0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002,
                     0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
                     0x2009, 0x200a,
                     #0x200b is in Other_Default_Ignorable_Code_Point in 4.1.0
                     0x2028, 0x2029, 0x202f, 0x205f, 0x3000]:
            assert api.Py_UNICODE_ISSPACE(unichr(char))
        assert not api.Py_UNICODE_ISSPACE(u'a')

        assert api.Py_UNICODE_ISALPHA(u'a')
        assert not api.Py_UNICODE_ISALPHA(u'0')
        assert api.Py_UNICODE_ISALNUM(u'a')
        assert api.Py_UNICODE_ISALNUM(u'0')
        assert not api.Py_UNICODE_ISALNUM(u'+')

        assert api.Py_UNICODE_ISDECIMAL(u'\u0660')
        assert not api.Py_UNICODE_ISDECIMAL(u'a')
        assert api.Py_UNICODE_ISDIGIT(u'9')
        assert not api.Py_UNICODE_ISDIGIT(u'@')
        assert api.Py_UNICODE_ISNUMERIC(u'9')
        assert not api.Py_UNICODE_ISNUMERIC(u'@')

        for char in [0x0a, 0x0d, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029]:
            assert api.Py_UNICODE_ISLINEBREAK(unichr(char))

        assert api.Py_UNICODE_ISLOWER(u'�')
        assert not api.Py_UNICODE_ISUPPER(u'�')
        assert api.Py_UNICODE_ISLOWER(u'a')
        assert not api.Py_UNICODE_ISUPPER(u'a')
        assert not api.Py_UNICODE_ISLOWER(u'�')
        assert api.Py_UNICODE_ISUPPER(u'�')
        assert not api.Py_UNICODE_ISTITLE(u'A')
        assert api.Py_UNICODE_ISTITLE(
            u'\N{LATIN CAPITAL LETTER L WITH SMALL LETTER J}')

    def test_TOLOWER(self, space, api):
        assert api.Py_UNICODE_TOLOWER(u'�') == u'�'
        assert api.Py_UNICODE_TOLOWER(u'�') == u'�'

    def test_TOUPPER(self, space, api):
        assert api.Py_UNICODE_TOUPPER(u'�') == u'�'
        assert api.Py_UNICODE_TOUPPER(u'�') == u'�'

    def test_TOTITLE(self, space, api):
        assert api.Py_UNICODE_TOTITLE(u'/') == u'/'
        assert api.Py_UNICODE_TOTITLE(u'�') == u'�'
        assert api.Py_UNICODE_TOTITLE(u'�') == u'�'

    def test_TODECIMAL(self, space, api):
        assert api.Py_UNICODE_TODECIMAL(u'6') == 6
        assert api.Py_UNICODE_TODECIMAL(u'A') == -1

    def test_TODIGIT(self, space, api):
        assert api.Py_UNICODE_TODIGIT(u'6') == 6
        assert api.Py_UNICODE_TODIGIT(u'A') == -1

    def test_TONUMERIC(self, space, api):
        assert api.Py_UNICODE_TONUMERIC(u'6') == 6.0
        assert api.Py_UNICODE_TONUMERIC(u'A') == -1.0
        assert api.Py_UNICODE_TONUMERIC(u'\N{VULGAR FRACTION ONE HALF}') == .5

    def test_transform_decimal(self, space, api):
        def transform_decimal(s):
            with rffi.scoped_unicode2wcharp(s) as u:
                return space.unwrap(
                    api.PyUnicode_TransformDecimalToASCII(u, len(s)))
        assert isinstance(transform_decimal(u'123'), unicode)
        assert transform_decimal(u'123') == u'123'
        assert transform_decimal(u'\u0663.\u0661\u0664') == u'3.14'
        assert transform_decimal(u"\N{EM SPACE}3.14\N{EN SPACE}") == (
            u"\N{EM SPACE}3.14\N{EN SPACE}")
        assert transform_decimal(u'123\u20ac') == u'123\u20ac'

    def test_fromobject(self, space, api):
        w_u = space.wrap(u'a')
        assert api.PyUnicode_FromObject(w_u) is w_u
        assert space.unwrap(
            api.PyUnicode_FromObject(space.wrapbytes('test'))) == "b'test'"

    def test_decode(self, space, api):
        b_text = rffi.str2charp('caf\x82xx')
        b_encoding = rffi.str2charp('cp437')
        assert space.unwrap(
            api.PyUnicode_Decode(b_text, 4, b_encoding, None)) == u'caf\xe9'

        w_text = api.PyUnicode_FromEncodedObject(space.wrapbytes("test"), b_encoding, None)
        assert space.isinstance_w(w_text, space.w_unicode)
        assert space.unwrap(w_text) == "test"

        assert api.PyUnicode_FromEncodedObject(space.wrap(u"test"), b_encoding, None) is None
        assert api.PyErr_Occurred() is space.w_TypeError
        assert api.PyUnicode_FromEncodedObject(space.wrap(1), b_encoding, None) is None
        assert api.PyErr_Occurred() is space.w_TypeError
        api.PyErr_Clear()

        rffi.free_charp(b_text)
        rffi.free_charp(b_encoding)

    def test_leak(self):
        size = 50
        raw_buf, gc_buf = rffi.alloc_buffer(size)
        for i in range(size): raw_buf[i] = 'a'
        str = rffi.str_from_buffer(raw_buf, gc_buf, size, size)
        rffi.keep_buffer_alive_until_here(raw_buf, gc_buf)

    def test_mbcs(self, space, api):
        if sys.platform != 'win32':
            py.test.skip("mcbs encoding only exists on Windows")
        # unfortunately, mbcs is locale-dependent.
        # This tests works at least on a Western Windows.
        unichars = u"abc" + unichr(12345)
        wbuf = rffi.unicode2wcharp(unichars)
        w_str = api.PyUnicode_EncodeMBCS(wbuf, 4, None)
        rffi.free_wcharp(wbuf)
        assert space.type(w_str) is space.w_str
        assert space.str_w(w_str) == "abc?"

    def test_escape(self, space, api):
        def test(ustr):
            w_ustr = space.wrap(ustr.decode('Unicode-Escape'))
            result = api.PyUnicode_AsUnicodeEscapeString(w_ustr)
            assert space.eq_w(space.wrapbytes(ustr), result)

        test('\\u674f\\u7f8e')
        test('\\u0105\\u0107\\u017c\\u017a')
        test('El Ni\\xf1o')

    def test_ascii(self, space, api):
        ustr = "abcdef"
        w_ustr = space.wrap(ustr.decode("ascii"))
        result = api.PyUnicode_AsASCIIString(w_ustr)
        
        assert space.eq_w(space.wrapbytes(ustr), result)

        w_ustr = space.wrap(u"abcd\xe9f")
        self.raises(space, api, UnicodeEncodeError, api.PyUnicode_AsASCIIString, w_ustr)

    def test_decode_utf16(self, space, api):
        def test(encoded, endian, realendian=None):
            encoded_charp = rffi.str2charp(encoded)
            strict_charp = rffi.str2charp("strict")
            if endian is not None:
                if endian < 0:
                    value = -1
                elif endian > 0:
                    value = 1
                else:
                    value = 0
                pendian = lltype.malloc(rffi.INTP.TO, 1, flavor='raw')
                pendian[0] = rffi.cast(rffi.INT, value)
            else:
                pendian = None

            w_ustr = api.PyUnicode_DecodeUTF16(encoded_charp, len(encoded), strict_charp, pendian)
            assert space.eq_w(space.call_method(w_ustr, 'encode', space.wrap('ascii')),
                              space.wrapbytes("abcd"))

            rffi.free_charp(encoded_charp)
            rffi.free_charp(strict_charp)
            if pendian:
                if realendian is not None:
                    assert rffi.cast(rffi.INT, realendian) == pendian[0]
                lltype.free(pendian, flavor='raw')

        test("\x61\x00\x62\x00\x63\x00\x64\x00", -1)

        test("\x61\x00\x62\x00\x63\x00\x64\x00", None)

        test("\x00\x61\x00\x62\x00\x63\x00\x64", 1)

        test("\xFE\xFF\x00\x61\x00\x62\x00\x63\x00\x64", 0, 1)
        test("\xFF\xFE\x61\x00\x62\x00\x63\x00\x64\x00", 0, -1)

    def test_decode_utf32(self, space, api):
        def test(encoded, endian, realendian=None):
            encoded_charp = rffi.str2charp(encoded)
            strict_charp = rffi.str2charp("strict")
            if endian is not None:
                if endian < 0:
                    value = -1
                elif endian > 0:
                    value = 1
                else:
                    value = 0
                pendian = lltype.malloc(rffi.INTP.TO, 1, flavor='raw')
                pendian[0] = rffi.cast(rffi.INT, value)
            else:
                pendian = None

            w_ustr = api.PyUnicode_DecodeUTF32(encoded_charp, len(encoded), strict_charp, pendian)
            assert space.eq_w(space.call_method(w_ustr, 'encode', space.wrap('ascii')),
                              space.wrapbytes("ab"))

            rffi.free_charp(encoded_charp)
            rffi.free_charp(strict_charp)
            if pendian:
                if realendian is not None:
                    assert rffi.cast(rffi.INT, realendian) == pendian[0]
                lltype.free(pendian, flavor='raw')

        test("\x61\x00\x00\x00\x62\x00\x00\x00", -1)

        test("\x61\x00\x00\x00\x62\x00\x00\x00", None)

        test("\x00\x00\x00\x61\x00\x00\x00\x62", 1)

        test("\x00\x00\xFE\xFF\x00\x00\x00\x61\x00\x00\x00\x62", 0, 1)
        test("\xFF\xFE\x00\x00\x61\x00\x00\x00\x62\x00\x00\x00", 0, -1)

    def test_compare(self, space, api):
        assert api.PyUnicode_Compare(space.wrap('a'), space.wrap('b')) == -1

    def test_copy(self, space, api):
        w_x = space.wrap(u"abcd\u0660")
        target_chunk, _ = rffi.alloc_unicodebuffer(space.int_w(space.len(w_x)))
        #lltype.malloc(Py_UNICODE, space.int_w(space.len(w_x)), flavor='raw')

        x_chunk = api.PyUnicode_AS_UNICODE(w_x)
        api.Py_UNICODE_COPY(target_chunk, x_chunk, 4)
        w_y = space.wrap(rffi.wcharpsize2unicode(target_chunk, 4))

        assert space.eq_w(w_y, space.wrap(u"abcd"))

        size = api.PyUnicode_GET_SIZE(w_x)
        api.Py_UNICODE_COPY(target_chunk, x_chunk, size)
        w_y = space.wrap(rffi.wcharpsize2unicode(target_chunk, size))

        assert space.eq_w(w_y, w_x)

        lltype.free(target_chunk, flavor='raw')

    def test_ascii_codec(self, space, api):
        s = 'abcdefg'
        data = rffi.str2charp(s)
        w_u = api.PyUnicode_DecodeASCII(data, len(s), lltype.nullptr(rffi.CCHARP.TO))
        assert space.eq_w(w_u, space.wrap(u"abcdefg"))
        rffi.free_charp(data)

        s = 'abcd\xFF'
        data = rffi.str2charp(s)
        self.raises(space, api, UnicodeDecodeError, api.PyUnicode_DecodeASCII,
                    data, len(s), lltype.nullptr(rffi.CCHARP.TO))
        rffi.free_charp(data)

        uni = u'abcdefg'
        data = rffi.unicode2wcharp(uni)
        w_s = api.PyUnicode_EncodeASCII(data, len(uni), lltype.nullptr(rffi.CCHARP.TO))
        assert space.eq_w(space.wrapbytes("abcdefg"), w_s)
        rffi.free_wcharp(data)

        u = u'�bcd�fg'
        data = rffi.unicode2wcharp(u)
        w_s = api.PyUnicode_EncodeASCII(data, len(u), lltype.nullptr(rffi.CCHARP.TO))
        self.raises(space, api, UnicodeEncodeError, api.PyUnicode_EncodeASCII,
                    data, len(u), lltype.nullptr(rffi.CCHARP.TO))
        rffi.free_wcharp(data)

    def test_latin1(self, space, api):
        s = 'abcdefg'
        data = rffi.str2charp(s)
        w_u = api.PyUnicode_DecodeLatin1(data, len(s), lltype.nullptr(rffi.CCHARP.TO))
        assert space.eq_w(w_u, space.wrap(u"abcdefg"))
        rffi.free_charp(data)

        uni = u'abcdefg'
        data = rffi.unicode2wcharp(uni)
        w_s = api.PyUnicode_EncodeLatin1(data, len(uni), lltype.nullptr(rffi.CCHARP.TO))
        assert space.eq_w(space.wrapbytes("abcdefg"), w_s)
        rffi.free_wcharp(data)

        ustr = "abcdef"
        w_ustr = space.wrap(ustr.decode("ascii"))
        result = api.PyUnicode_AsLatin1String(w_ustr)
        assert space.eq_w(space.wrapbytes(ustr), result)

    def test_format(self, space, api):
        w_format = space.wrap(u'hi %s')
        w_args = space.wrap((u'test',))
        w_formated = api.PyUnicode_Format(w_format, w_args)
        assert space.unwrap(w_formated) == space.unwrap(space.mod(w_format, w_args))

    def test_join(self, space, api):
        w_sep = space.wrap(u'<sep>')
        w_seq = space.wrap([u'a', u'b'])
        w_joined = api.PyUnicode_Join(w_sep, w_seq)
        assert space.unwrap(w_joined) == u'a<sep>b'

    def test_fromordinal(self, space, api):
        w_char = api.PyUnicode_FromOrdinal(65)
        assert space.unwrap(w_char) == u'A'
        w_char = api.PyUnicode_FromOrdinal(0)
        assert space.unwrap(w_char) == u'\0'
        w_char = api.PyUnicode_FromOrdinal(0xFFFF)
        assert space.unwrap(w_char) == u'\uFFFF'

    def test_replace(self, space, api):
        w_str = space.wrap(u"abababab")
        w_substr = space.wrap(u"a")
        w_replstr = space.wrap(u"z")
        assert u"zbzbabab" == space.unwrap(
            api.PyUnicode_Replace(w_str, w_substr, w_replstr, 2))
        assert u"zbzbzbzb" == space.unwrap(
            api.PyUnicode_Replace(w_str, w_substr, w_replstr, -1))

    def test_tailmatch(self, space, api):
        w_str = space.wrap(u"abcdef")
        # prefix match
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 2, 9, -1) == 1
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 2, 4, -1) == 0 # ends at 'd'
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 1, 6, -1) == 0 # starts at 'b'
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cdf"), 2, 6, -1) == 0
        # suffix match
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 1, 5,  1) == 1
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 3, 5,  1) == 0 # starts at 'd'
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("cde"), 1, 6,  1) == 0 # ends at 'f'
        assert api.PyUnicode_Tailmatch(w_str, space.wrap("bde"), 1, 5,  1) == 0
        # type checks
        self.raises(space, api, TypeError,
                    api.PyUnicode_Tailmatch, w_str, space.wrap(3), 2, 10, 1)
        self.raises(space, api, TypeError,
                    api.PyUnicode_Tailmatch, space.wrap(3), space.wrap("abc"),
                    2, 10, 1)

    def test_count(self, space, api):
        w_str = space.wrap(u"abcabdab")
        assert api.PyUnicode_Count(w_str, space.wrap(u"ab"), 0, -1) == 2
        assert api.PyUnicode_Count(w_str, space.wrap(u"ab"), 0, 2) == 1
        assert api.PyUnicode_Count(w_str, space.wrap(u"ab"), -5, 30) == 2

    def test_find(self, space, api):
        w_str = space.wrap(u"abcabcd")
        assert api.PyUnicode_Find(w_str, space.wrap(u"c"), 0, 7, 1) == 2
        assert api.PyUnicode_Find(w_str, space.wrap(u"c"), 3, 7, 1) == 5
        assert api.PyUnicode_Find(w_str, space.wrap(u"c"), 0, 7, -1) == 5
        assert api.PyUnicode_Find(w_str, space.wrap(u"c"), 3, 7, -1) == 5
        assert api.PyUnicode_Find(w_str, space.wrap(u"c"), 0, 4, -1) == 2
        assert api.PyUnicode_Find(w_str, space.wrap(u"z"), 0, 4, -1) == -1

    def test_split(self, space, api):
        w_str = space.wrap(u"a\nb\nc\nd")
        assert "['a', 'b', 'c', 'd']" == space.unwrap(space.repr(
                api.PyUnicode_Split(w_str, space.wrap('\n'), -1)))
        assert r"['a', 'b', 'c\nd']" == space.unwrap(space.repr(
                api.PyUnicode_Split(w_str, space.wrap('\n'), 2)))
        assert r"['a', 'b', 'c d']" == space.unwrap(space.repr(
                api.PyUnicode_Split(space.wrap(u'a\nb  c d'), None, 2)))
        assert "['a', 'b', 'c', 'd']" == space.unwrap(space.repr(
                api.PyUnicode_Splitlines(w_str, 0)))
        assert r"['a\n', 'b\n', 'c\n', 'd']" == space.unwrap(space.repr(
                api.PyUnicode_Splitlines(w_str, 1)))
