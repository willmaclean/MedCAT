import json
import os
import sys
import unittest
import tempfile
from medcat.vocab import Vocab
from medcat.cdb import CDB
from medcat.cat import CAT
from medcat.utils.checkpoint import Checkpoint


class CATTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cdb = CDB.load(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "examples", "cdb.dat"))
        cls.vocab = Vocab.load(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "examples", "vocab.dat"))
        cls.cdb.config.general["spacy_model"] = "en_core_web_md"
        cls.cdb.config.ner['min_name_len'] = 2
        cls.cdb.config.ner['upper_case_limit_len'] = 3
        cls.cdb.config.general['spell_check'] = True
        cls.cdb.config.linking['train_count_threshold'] = 10
        cls.cdb.config.linking['similarity_threshold'] = 0.3
        cls.cdb.config.linking['train'] = True
        cls.cdb.config.linking['disamb_length_limit'] = 5
        cls.cdb.config.general['full_unlink'] = True
        cls.undertest = CAT(cdb=cls.cdb, config=cls.cdb.config, vocab=cls.vocab)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.undertest.destroy_pipe()

    def tearDown(self) -> None:
        self.cdb.config.annotation_output['include_text_in_output'] = False

    def test_callable_with_single_text(self):
        text = "The dog is sitting outside the house."
        doc = self.undertest(text)
        self.assertEqual(text, doc.text)

    def test_callable_with_single_empty_text(self):
        self.assertIsNone(self.undertest(""))

    def test_callable_with_single_none_text(self):
        self.assertIsNone(self.undertest(None))

    def test_multiprocessing(self):
        in_data = [
            (1, "The dog is sitting outside the house and second csv."),
            (2, ""),
            (3, None)
        ]
        out = self.undertest.multiprocessing(in_data, nproc=1)

        self.assertEqual(3, len(out))
        self.assertEqual(1, len(out[1]['entities']))
        self.assertEqual(0, len(out[2]['entities']))
        self.assertEqual(0, len(out[3]['entities']))

    def test_multiprocessing_pipe(self):
        in_data = [
            (1, "The dog is sitting outside the house and second csv."),
            (2, "The dog is sitting outside the house."),
            (3, "The dog is sitting outside the house."),
        ]
        out = self.undertest.multiprocessing_pipe(in_data, nproc=2, return_dict=False)
        self.assertTrue(type(out) == list)
        self.assertEqual(3, len(out))
        self.assertEqual(1, out[0][0])
        self.assertEqual('second csv', out[0][1]['entities'][0]['source_value'])
        self.assertEqual(2, out[1][0])
        self.assertEqual({'entities': {}, 'tokens': []}, out[1][1])
        self.assertEqual(3, out[2][0])
        self.assertEqual({'entities': {}, 'tokens': []}, out[2][1])

    def test_multiprocessing_pipe_with_malformed_texts(self):
        in_data = [
            (1, "The dog is sitting outside the house."),
            (2, ""),
            (3, None),
        ]
        out = self.undertest.multiprocessing_pipe(in_data, nproc=1, batch_size=1, return_dict=False)
        self.assertTrue(type(out) == list)
        self.assertEqual(3, len(out))
        self.assertEqual(1, out[0][0])
        self.assertEqual({'entities': {}, 'tokens': []}, out[0][1])
        self.assertEqual(2, out[1][0])
        self.assertEqual({'entities': {}, 'tokens': []}, out[1][1])
        self.assertEqual(3, out[2][0])
        self.assertEqual({'entities': {}, 'tokens': []}, out[2][1])

    def test_multiprocessing_pipe_return_dict(self):
        in_data = [
            (1, "The dog is sitting outside the house."),
            (2, "The dog is sitting outside the house."),
            (3, "The dog is sitting outside the house.")
        ]
        out = self.undertest.multiprocessing_pipe(in_data, nproc=2, return_dict=True)
        self.assertTrue(type(out) == dict)
        self.assertEqual(3, len(out))
        self.assertEqual({'entities': {}, 'tokens': []}, out[1])
        self.assertEqual({'entities': {}, 'tokens': []}, out[2])
        self.assertEqual({'entities': {}, 'tokens': []}, out[3])

    def test_train(self):
        ckpt_steps = 2
        nepochs = 3
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path, steps=ckpt_steps)
        self.undertest.cdb.print_stats()
        self.undertest.train(["The dog is not a house"] * 20, nepochs=nepochs, checkpoint=checkpoint)
        self.undertest.cdb.print_stats()
        checkpoints = [f for f in os.listdir(ckpt_dir_path) if "checkpoint-" in f]

        self.assertEqual(1, len(checkpoints))
        self.assertEqual(f"checkpoint-{ckpt_steps}-{nepochs * 20}", checkpoints[0])

    def test_resume_training(self):
        nepochs_train = 1
        nepochs_retrain = 1
        ckpt_steps = 3
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path, steps=ckpt_steps, max_to_keep=sys.maxsize)
        self.undertest.cdb.print_stats()
        self.undertest.train(["The dog is not a house"] * 20,
                             nepochs=nepochs_train,
                             checkpoint=checkpoint,
                             is_resumed=False)
        self.undertest.cdb.print_stats()
        self.undertest.train(["The dog is not a house"] * 20,
                             nepochs=nepochs_train+nepochs_retrain,
                             checkpoint=checkpoint,
                             is_resumed=True)
        checkpoints = [f for f in os.listdir(ckpt_dir_path) if "checkpoint-" in f]
        self.assertEqual(13, len(checkpoints))
        self.assertTrue("checkpoint-%s-3" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-6" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-9" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-12" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-15" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-18" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-21" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-24" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-27" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-30" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-33" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-36" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-39" % ckpt_steps in checkpoints)

    def test_resume_training_on_absent_checkpoints(self):
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path)
        with self.assertRaises(Exception) as e:
            self.undertest.train(["The dog is not a house"] * 40, checkpoint=checkpoint, is_resumed=True)
        self.assertEqual("Checkpoints not found. You need to train from scratch.", str(e.exception))

    def test_train_keep_n_checkpoints(self):
        ckpt_steps = 2
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path, steps=ckpt_steps, max_to_keep=2)
        self.undertest.cdb.print_stats()
        self.undertest.train(["The dog is not a house"] * 20, checkpoint=checkpoint)
        self.undertest.cdb.print_stats()
        checkpoints = [f for f in os.listdir(ckpt_dir_path) if "checkpoint-" in f]
        self.assertEqual(2, len(checkpoints))
        self.assertTrue("checkpoint-%s-18" % ckpt_steps in checkpoints)
        self.assertTrue("checkpoint-%s-20" % ckpt_steps in checkpoints)

    def test_get_entities(self):
        text = "The dog is sitting outside the house."
        out = self.undertest.get_entities(text)
        self.assertEqual({}, out["entities"])
        self.assertEqual([], out["tokens"])
        self.assertFalse("text" in out)

    def test_get_entities_including_text(self):
        self.cdb.config.annotation_output['include_text_in_output'] = True
        text = "The dog is sitting outside the house."
        out = self.undertest.get_entities(text)
        self.assertEqual({}, out["entities"])
        self.assertEqual([], out["tokens"])
        self.assertTrue(text in out["text"])

    def test_get_entities_multi_texts(self):
        in_data = [(1, "The dog is sitting outside the house."), (2, ""), (3, "The dog is sitting outside the house.")]
        out = self.undertest.get_entities_multi_texts(in_data, n_process=2)
        self.assertEqual(3, len(out))
        self.assertFalse("text" in out[0])
        self.assertFalse("text" in out[1])
        self.assertFalse("text" in out[2])

    def test_get_entities_multi_texts_including_text(self):
        self.cdb.config.annotation_output['include_text_in_output'] = True
        in_data = [(1, "The dog is sitting outside the house."), (2, ""), (3, None)]
        out = self.undertest.get_entities_multi_texts(in_data, n_process=2)
        self.assertEqual(3, len(out))
        self.assertTrue("text" in out[0])
        self.assertFalse("text" in out[1])
        self.assertFalse("text" in out[2])

    def test_train_supervised(self):
        nepochs = 3
        num_of_documents = 27
        data_path = os.path.join(os.path.dirname(__file__), "resources", "medcat_trainer_export.json")
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path, steps=1, max_to_keep=sys.maxsize)
        fp, fn, tp, p, r, f1, cui_counts, examples = self.undertest.train_supervised(data_path,
                                                                                     checkpoint=checkpoint,
                                                                                     nepochs=nepochs)
        checkpoints = [f for f in os.listdir(ckpt_dir_path) if "checkpoint-" in f]
        self.assertEqual({}, fp)
        self.assertEqual({}, fn)
        self.assertEqual({}, tp)
        self.assertEqual({}, p)
        self.assertEqual({}, r)
        self.assertEqual({}, f1)
        self.assertEqual({}, cui_counts)
        self.assertEqual({}, examples)
        self.assertEqual(nepochs * num_of_documents, len(checkpoints))
        for step in range(1, nepochs * num_of_documents + 1):
            self.assertTrue(f"checkpoint-1-{step}" in checkpoints)

    def test_resume_supervised_training(self):
        nepochs_train = 1
        nepochs_retrain = 2
        num_of_documents = 27
        data_path = os.path.join(os.path.dirname(__file__), "resources", "medcat_trainer_export.json")
        ckpt_dir_path = tempfile.TemporaryDirectory().name
        checkpoint = Checkpoint(dir_path=ckpt_dir_path, steps=1, max_to_keep=sys.maxsize)
        self.undertest.train_supervised(data_path,
                                        checkpoint=checkpoint,
                                        nepochs=nepochs_train)
        fp, fn, tp, p, r, f1, cui_counts, examples = self.undertest.train_supervised(data_path,
                                                                                     checkpoint=checkpoint,
                                                                                     nepochs=nepochs_train+nepochs_retrain,
                                                                                     is_resumed=True)
        checkpoints = [f for f in os.listdir(ckpt_dir_path) if "checkpoint-" in f]
        self.assertEqual({}, fp)
        self.assertEqual({}, fn)
        self.assertEqual({}, tp)
        self.assertEqual({}, p)
        self.assertEqual({}, r)
        self.assertEqual({}, f1)
        self.assertEqual({}, cui_counts)
        self.assertEqual({}, examples)
        self.assertEqual((nepochs_train + nepochs_retrain) * num_of_documents, len(checkpoints))
        for step in range(1, (nepochs_train + nepochs_retrain) * num_of_documents):
            self.assertTrue(f"checkpoint-1-{step}" in checkpoints)

    def test_no_error_handling_on_none_input(self):
        out = self.undertest.get_entities(None)
        self.assertEqual({}, out["entities"])
        self.assertEqual([], out["tokens"])

    def test_no_error_handling_on_empty_string_input(self):
        out = self.undertest.get_entities("")
        self.assertEqual({}, out["entities"])
        self.assertEqual([], out["tokens"])

    def test_no_raise_on_single_process_with_none(self):
        out = self.undertest.get_entities_multi_texts(["The dog is sitting outside the house.", None, "The dog is sitting outside the house."], n_process=1, batch_size=2)
        self.assertEqual(3, len(out))
        self.assertEqual({}, out[0]["entities"])
        self.assertEqual([], out[0]["tokens"])
        self.assertEqual({}, out[1]["entities"])
        self.assertEqual([], out[1]["tokens"])
        self.assertEqual({}, out[2]["entities"])
        self.assertEqual([], out[2]["tokens"])

    def test_no_raise_on_single_process_with_empty_string(self):
        out = self.undertest.get_entities_multi_texts(["The dog is sitting outside the house.", "", "The dog is sitting outside the house."], n_process=1, batch_size=2)
        self.assertEqual(3, len(out))
        self.assertEqual({}, out[0]["entities"])
        self.assertEqual([], out[0]["tokens"])
        self.assertEqual({}, out[1]["entities"])
        self.assertEqual([], out[1]["tokens"])
        self.assertEqual({}, out[2]["entities"])
        self.assertEqual([], out[2]["tokens"])

    def test_error_handling_multi_processes(self):
        self.cdb.config.annotation_output['include_text_in_output'] = True
        out = self.undertest.get_entities_multi_texts([
                                           (1, "The dog is sitting outside the house 1."),
                                           (2, "The dog is sitting outside the house 2."),
                                           (3, "The dog is sitting outside the house 3."),
                                           (4, None),
                                           (5, None)], n_process=2, batch_size=2)
        self.assertEqual(5, len(out))
        self.assertEqual({}, out[0]["entities"])
        self.assertEqual([], out[0]["tokens"])
        self.assertTrue("The dog is sitting outside the house 1.", out[0]["text"])
        self.assertEqual({}, out[1]["entities"])
        self.assertEqual([], out[1]["tokens"])
        self.assertTrue("The dog is sitting outside the house 2.", out[1]["text"])
        self.assertEqual({}, out[2]["entities"])
        self.assertEqual([], out[2]["tokens"])
        self.assertTrue("The dog is sitting outside the house 3.", out[2]["text"])
        self.assertEqual({}, out[3]["entities"])
        self.assertEqual([], out[3]["tokens"])
        self.assertFalse("text" in out[3])
        self.assertEqual({}, out[4]["entities"])
        self.assertEqual([], out[4]["tokens"])
        self.assertFalse("text" in out[4])

    def test_create_model_pack(self):
        save_dir_path = tempfile.TemporaryDirectory()
        full_model_pack_name = self.undertest.create_model_pack(save_dir_path.name, model_pack_name="mp_name")
        pack = [f for f in os.listdir(save_dir_path.name)]
        self.assertTrue(full_model_pack_name in pack)
        self.assertTrue(f'{full_model_pack_name}.zip' in pack)
        contents = [f for f in os.listdir(os.path.join(save_dir_path.name, full_model_pack_name))]
        self.assertTrue("cdb.dat" in contents)
        self.assertTrue("vocab.dat" in contents)
        self.assertTrue("model_card.json" in contents)
        with open(os.path.join(save_dir_path.name, full_model_pack_name, "model_card.json")) as file:
            model_card = json.load(file)
        self.assertTrue("MedCAT Version" in model_card)

    def test_load_model_pack(self):
        save_dir_path = tempfile.TemporaryDirectory()
        full_model_pack_name = self.undertest.create_model_pack(save_dir_path.name, model_pack_name="mp_name")
        cat = self.undertest.load_model_pack(os.path.join(save_dir_path.name, f"{full_model_pack_name}.zip"))
        self.assertTrue(isinstance(cat, CAT))

    def test_hashing(self):
        save_dir_path = tempfile.TemporaryDirectory()
        full_model_pack_name = self.undertest.create_model_pack(save_dir_path.name, model_pack_name="mp_name")
        cat = self.undertest.load_model_pack(os.path.join(save_dir_path.name, f"{full_model_pack_name}.zip"))
        self.assertEqual(cat.get_hash(), cat.config.version['id'])


if __name__ == '__main__':
    unittest.main()
